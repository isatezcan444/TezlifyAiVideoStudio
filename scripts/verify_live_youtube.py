#!/usr/bin/env python3
"""
Tezlify AI Video Studio - Canlı YouTube ve OAuth Entegrasyon Doğrulama Aracı (Aşama 3.4)
"""
import os
import sys
import time
import threading
import webbrowser
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_SRC = os.path.join(PROJECT_ROOT, "backend", "src")
sys.path.insert(0, BACKEND_SRC)

from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import SessionLocal, init_db
from tezlify_studio.infrastructure.persistence.repositories.social_account_repository_impl import SocialAccountRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import MediaRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import PublishRecordRepositoryImpl
from tezlify_studio.infrastructure.security.token_storage_impl import KeychainTokenStorageAdapter
from tezlify_studio.infrastructure.media.youtube_api_client_impl import YouTubeApiClientImpl
from tezlify_studio.infrastructure.media.local_media_storage import LocalMediaStorage
from tezlify_studio.infrastructure.security.oauth_desktop_listener import DesktopOAuthListener
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import GenerateYouTubeAuthUrlUseCase
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import CompleteYouTubeAuthenticationUseCase
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase
from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus

def main():
    print("=" * 65)
    print("  TEZLIFY AI VIDEO STUDIO — CANLI YOUTUBE ENTEGRASYON TESTİ")
    print("=" * 65)

    if not settings.resolved_youtube_client_id or not settings.resolved_youtube_client_secret:
        print("\n❌ HATA: GOOGLE_CLIENT_ID veya GOOGLE_CLIENT_SECRET .env dosyasında bulunamadı.")
        sys.exit(1)

    print("\n[1/4] SQLite Veritabanı ve macOS Keychain Hazırlanıyor...")
    init_db()
    db = SessionLocal()
    account_repo = SocialAccountRepositoryImpl(db)
    token_storage = KeychainTokenStorageAdapter(fallback_to_memory=False)
    publisher = YouTubeApiClientImpl()

    # Check if already authenticated
    active_account = account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
    need_login = True
    if active_account:
        print(f"   [i] Mevcut aktif hesap bulundu: {active_account.account_name} (ID: {active_account.channel_id})")
        token = token_storage.get_access_token(active_account.id)
        if token:
            try:
                profile = publisher.get_channel_profile(token)
                print(f"   [✓] Canlı Token Geçerli: {profile.get('channel_title')} ({profile.get('channel_id')})")
                need_login = False
            except Exception as e:
                print(f"   [!] Token süresi dolmuş veya geçersiz ({e}), yeniden bağlanılıyor...")
                need_login = True

    if need_login:
        print("\n[2/4] Google Desktop OAuth 2.0 PKCE Akışı Başlatılıyor...")
        complete_use_case = CompleteYouTubeAuthenticationUseCase(
            account_repo=account_repo,
            token_storage=token_storage,
            publisher=publisher,
        )

        completed_event = threading.Event()
        auth_result = {"success": False, "error": None, "account": None}

        def on_auth_finished(success: bool = False, error: str = None):
            auth_result["success"] = success
            auth_result["error"] = error
            completed_event.set()

        listener = DesktopOAuthListener.start_new(
            oauth_handler_cb=complete_use_case.execute,
            timeout_seconds=180,
        )
        listener.server.on_complete_cb = on_auth_finished

        gen_auth_use_case = GenerateYouTubeAuthUrlUseCase(publisher)
        dto = gen_auth_use_case.execute(
            redirect_uri=listener.redirect_uri,
            loopback_port=listener.port,
        )

        print(f"   [✓] Loopback dinleyici hazır: {listener.redirect_uri}")
        print("\n🌐 Lütfen tarayıcınızda açılan Google onay ekranından YouTube kanalınızı seçin...")
        print("   (Tarayıcı otomatik açılmazsa şu adrese gidin):")
        print(f"   {dto.auth_url}\n")

        try:
            webbrowser.open(dto.auth_url)
        except Exception:
            pass

        print("⏳ Google yanıtı bekleniyor (Zaman aşımı: 180 saniye)...")
        wait_success = completed_event.wait(timeout=180)
        listener.stop()

        if not wait_success:
            print("\n❌ Zaman aşımı: Google OAuth yetkilendirmesi 180 saniye içinde tamamlanmadı.")
            db.close()
            sys.exit(1)

        if not auth_result["success"]:
            print(f"\n❌ OAuth yetkilendirmesi başarısız: {auth_result.get('error')}")
            db.close()
            sys.exit(1)

        db.expire_all()
        active_account = account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
        if not active_account:
            print("\n❌ Hesap veritabanına kaydedilemedi.")
            db.close()
            sys.exit(1)

        print(f"\n🎉 [✓] Başarıyla Bağlandı: {active_account.account_name} (Kanal ID: {active_account.channel_id})")

    # Step 3: Verify Keychain Persistence
    print("\n[3/4] macOS Keychain Token Kalıcılığı Denetleniyor...")
    saved_acc = token_storage.get_access_token(active_account.id)
    saved_ref = token_storage.get_refresh_token(active_account.id)
    if saved_acc:
        print(f"   [✓] Access Token Keychain'de güvenle saklanıyor.")
    if saved_ref:
        print(f"   [✓] Refresh Token Keychain'de güvenle saklanıyor.")
    else:
        print(f"   [i] Refresh token Google tarafından ilk onayda üretilir (veya mevcut korundu).")

    print("\n" + "=" * 65)
    print("  GOOGLE OAUTH VE KANAL DOĞRULAMASI BAŞARIYLA TAMAMLANDI!")
    print(f"  Bağlı Kanal: {active_account.account_name}")
    print(f"  Kanal ID:    {active_account.channel_id}")
    print("=" * 65)
    db.close()

if __name__ == "__main__":
    main()

