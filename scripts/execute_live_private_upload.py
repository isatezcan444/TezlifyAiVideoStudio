#!/usr/bin/env python3
"""
Tezlify AI Video Studio - Canlı YouTube Private Test Videosu Yükleme Aracı (Aşama 3.4)
"""
import os
import sys

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
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase
from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PublishStatus

def main():
    print("=" * 65)
    print("  TEZLIFY AI VIDEO STUDIO — CANLI PRIVATE TEST YÜKLEMESİ")
    print("=" * 65)

    init_db()
    db = SessionLocal()
    account_repo = SocialAccountRepositoryImpl(db)
    media_repo = MediaRepositoryImpl(db)
    publish_repo = PublishRecordRepositoryImpl(db)
    token_storage = KeychainTokenStorageAdapter(fallback_to_memory=False)
    storage = LocalMediaStorage(settings.media_dir, settings.temp_dir)
    publisher = YouTubeApiClientImpl()

    # 1. Verify Active YouTube Account
    account = account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
    if not account:
        print("❌ HATA: Aktif YouTube hesabı bulunamadı.")
        db.close()
        sys.exit(1)

    print(f"\n[1/5] Yetkili YouTube Hesabı Doğrulanıyor...")
    print(f"   [✓] Kanal Adı: {account.account_name}")
    print(f"   [✓] Kanal ID:  {account.channel_id}")

    # 2. Verify Media Asset
    test_media_id = "211fefdd-e27f-4642-a022-d353260d4867"
    media = media_repo.get_by_id(test_media_id)
    if not media:
        print(f"❌ HATA: Test medya varlığı bulunamadı: {test_media_id}")
        db.close()
        sys.exit(1)

    print(f"\n[2/5] Test Video Dosyası Doğrulanıyor...")
    print(f"   [✓] Medya ID:   {media.id}")
    print(f"   [✓] Dosya Adı:  {media.filename}")
    print(f"   [✓] Boyut:      {media.file_size_bytes} bayt ({media.file_size_bytes / 1024:.1f} KB)")
    print(f"   [✓] Çözünürlük: {media.metadata.width}x{media.metadata.height}")
    print(f"   [✓] Süre:       {media.metadata.duration_seconds}s")

    # 3. Prepare Publish Request (Strictly PRIVATE)
    title = "[TEST] Tezlify AI Video Studio Verification"
    description = (
        "Tezlify AI Video Studio - Aşama 3.4 Canlı Entegrasyon Doğrulama Testi.\n"
        "Bu video, yerel stüdyo yazılımının Google Resumable Upload ve OAuth 2.0 PKCE "
        "kabiliyetlerini test etmek amacıyla otomatik yüklenmiştir."
    )
    req = StartPublishRequestDTO(
        media_asset_id=media.id,
        title=title,
        description=description,
        tags=["tezlify", "studio", "test", "verification"],
        category_id="28",  # Science & Technology
        privacy_status="private",
    )

    def repo_factory():
        s_db = SessionLocal()
        return PublishRecordRepositoryImpl(s_db), lambda: s_db.close()

    publish_use_case = PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=storage,
        account_repo=account_repo,
        publish_repo=publish_repo,
        token_storage=token_storage,
        publisher=publisher,
        chunk_size=4 * 1024 * 1024,
        repo_factory=repo_factory,
    )

    # 4. Execute Resumable Upload
    print(f"\n[3/5] Google Resumable Upload Başlatılıyor (Gizlilik: PRIVATE)...")
    print("   [i] Resumable upload oturumu açılıyor ve video parçaları gönderiliyor...")
    
    record_dto = publish_use_case.execute(req, async_upload=False)
    
    print(f"   [✓] Yükleme Tamamlandı! Durum: {record_dto.status}")
    print(f"   [✓] YouTube Video ID:  {record_dto.external_video_id}")
    print(f"   [✓] YouTube Video URL: {record_dto.external_video_url}")

    # 5. Live Verification via YouTube Data API
    print(f"\n[4/5] YouTube Data API Üzerinden Canlı Durum Sorgulanıyor...")
    access_token = token_storage.get_access_token(account.id)
    video_details = publisher.get_video_details(access_token, record_dto.external_video_id)

    status_obj = video_details.get("status", {})
    snippet_obj = video_details.get("snippet", {})
    actual_privacy = status_obj.get("privacyStatus")
    actual_title = snippet_obj.get("title")
    upload_status = status_obj.get("uploadStatus")

    print(f"   [✓] Doğrulanan Başlık:      {actual_title}")
    print(f"   [✓] Doğrulanan Gizlilik:    {actual_privacy}")
    print(f"   [✓] Yükleme Durumu:         {upload_status}")

    if actual_privacy != "private":
        print(f"❌ KRİTİK GÜVENLİK UYARISI: Gizlilik private değil ({actual_privacy})!")
        sys.exit(1)

    # 6. Database Verification
    print(f"\n[5/5] Yerel SQLite PublishRecord Doğrulanıyor...")
    db.expire_all()
    saved_record = publish_repo.get_by_id(record_dto.id)
    print(f"   [✓] Kayıt ID:             {saved_record.id}")
    print(f"   [✓] Durum:                {saved_record.status.value}")
    print(f"   [✓] İlerleme:             %{saved_record.progress_percentage}")
    print(f"   [✓] Yüklenen Bayt:        {saved_record.uploaded_bytes} / {saved_record.total_bytes}")
    print(f"   [✓] Harici Video ID:      {saved_record.external_video_id}")
    print(f"   [✓] Hata Kodu / Mesaj:    {saved_record.error_code} / {saved_record.error_message}")

    print("\n" + "=" * 65)
    print("  🎉 TEZLIFY AI VIDEO STUDIO — CANLI YAYIN BAŞARIYLA TAMAMLANDI!")
    print(f"  YouTube Video ID:  {record_dto.external_video_id}")
    print(f"  YouTube Studio:    https://studio.youtube.com/video/{record_dto.external_video_id}/edit")
    print(f"  İzleme Bağlantısı: {record_dto.external_video_url}")
    print(f"  Gizlilik Derecesi: {actual_privacy.upper()} (Gizli)")
    print("=" * 65)

    db.close()

if __name__ == "__main__":
    main()
