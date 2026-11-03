#!/usr/bin/env python3
import os
import sys
import time
import urllib.request
import urllib.error
import json
from tezlify_studio.presentation.api.app import app
from fastapi.testclient import TestClient

def run_verification():
    print("=" * 65)
    print("  TEZLIFY AI VIDEO STUDIO - UÇTAN UCA DOĞRULAMA (E2E TEST)")
    print("=" * 65)

    client = TestClient(app)

    # 1. Health check
    print("\n1. Health Check Test Ediliyor...")
    res = client.get("/api/v1/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print(f"   [✓] Health Check OK: {res.json()}")

    # 2. System Status
    print("\n2. Sistem Durumu Test Ediliyor...")
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200, f"System status failed: {res.text}"
    status_data = res.json()
    print(f"   [✓] OS: {status_data['os_name']}")
    print(f"   [✓] Python: {status_data['python_version']}")
    print(f"   [✓] Storage Path: {status_data['data_dir']}")

    # 3. Video Upload Flow with sample MP4
    print("\n3. Gerçek Video Yükleme Akışı Test Ediliyor...")
    sample_path = os.path.join(os.path.dirname(__file__), "..", "data", "temp", "sample_test_video.mp4")
    assert os.path.exists(sample_path), f"Sample video not found at: {sample_path}"

    with open(sample_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/media/upload",
            files={"file": ("sample_test_video.mp4", f, "video/mp4")}
        )
    assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
    asset = upload_res.json()
    asset_id = asset["id"]
    print(f"   [✓] Video Yüklendi! ID: {asset_id}")
    print(f"   [✓] Dosya Adı: {asset['original_filename']}")
    print(f"   [✓] Süre: {asset['metadata']['duration_seconds']}s")
    print(f"   [✓] Çözünürlük: {asset['metadata']['resolution_label']}")
    print(f"   [✓] SHA-256 Hash: {asset['sha256_hash'][:16]}...")

    # 4. Media Library Listing
    print("\n4. Medya Kütüphanesinde Listeleme Doğrulanıyor...")
    list_res = client.get("/api/v1/media")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(item["id"] == asset_id for item in items)
    print(f"   [✓] Kütüphanede bulundu (Toplam {len(items)} video).")

    # 5. Video HTTP Range Streaming (Seek Test)
    print("\n5. Video HTTP Range Streaming (İleri-Geri Sarma) Test Ediliyor...")
    range_res = client.get(f"/api/v1/media/{asset_id}/stream", headers={"Range": "bytes=0-1023"})
    assert range_res.status_code == 206, f"Range stream failed: {range_res.status_code}"
    assert len(range_res.content) == 1024
    assert "bytes 0-1023/" in range_res.headers.get("Content-Range", "")
    print(f"   [✓] HTTP 206 Partial Content (Bytes 0-1023) başarıyla iletildi.")

    # 6. Duplicate Detection Test
    print("\n6. Mükerrer Video Tespiti (Duplicate Hash) Test Ediliyor...")
    with open(sample_path, "rb") as f:
        dup_res = client.post(
            "/api/v1/media/upload",
            files={"file": ("sample_test_video_duplicate.mp4", f, "video/mp4")}
        )
    assert dup_res.status_code == 409, f"Duplicate check failed: {dup_res.text}"
    assert dup_res.json()["error_code"] == "DUPLICATE_MEDIA"
    print(f"   [✓] HTTP 409 DUPLICATE_MEDIA başarıyla engellendi.")

    # 7. Persistence Check Across Session
    print("\n7. Kalıcılık (Persistence) Doğrulanıyor...")
    from tezlify_studio.infrastructure.persistence.database import SessionLocal
    from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import MediaRepositoryImpl
    db = SessionLocal()
    repo = MediaRepositoryImpl(db)
    persisted = repo.get_by_id(asset_id)
    assert persisted is not None
    assert persisted.sha256_hash == asset["sha256_hash"]
    db.close()
    print(f"   [✓] SQLite veritabanında kayıt kalıcı olarak korundu.")

    # 8. Deletion & Cleanup
    print("\n8. Güvenli Silme ve Dosya Temizliği Test Ediliyor...")
    file_on_disk = asset["file_path"]
    assert os.path.exists(file_on_disk)
    del_res = client.delete(f"/api/v1/media/{asset_id}")
    assert del_res.status_code == 200
    assert not os.path.exists(file_on_disk)
    print(f"   [✓] Medya kaydı ve diskteki dosya güvenle silindi.")

    print("\n" + "=" * 65)
    print("  🎉 TÜM UÇTAN UCA TESTLER BAŞARIYLA TAMAMLANDI!")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    run_verification()
