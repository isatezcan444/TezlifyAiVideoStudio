import os
import io
import pytest
from fastapi.testclient import TestClient
from tezlify_studio.presentation.api.app import app

client = TestClient(app)

def test_api_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Tezlify" in data["app"]

def test_api_system_status():
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "os_name" in data
    assert "python_version" in data
    assert "disk_free_gb" in data

def test_api_video_upload_stream_and_delete_flow():
    # 1. Prepare sample video bytes
    sample_video_bytes = b"ftypmp42\x00\x00\x00\x00isommp42moov\x00\x00\x00lmvhd" + (b"\x00" * 200)

    # 2. Upload video
    files = {"file": ("test_presentation.mp4", io.BytesIO(sample_video_bytes), "video/mp4")}
    upload_res = client.post("/api/v1/media/upload", files=files)
    assert upload_res.status_code == 201
    media_data = upload_res.json()
    media_id = media_data["id"]
    assert media_data["original_filename"] == "test_presentation.mp4"
    assert media_data["status"] == "ready"
    assert media_data["file_size_bytes"] == len(sample_video_bytes)

    # 3. List media
    list_res = client.get("/api/v1/media")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(item["id"] == media_id for item in items)

    # 4. Get media details
    detail_res = client.get(f"/api/v1/media/{media_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == media_id

    # 5. Stream video (full)
    stream_res = client.get(f"/api/v1/media/{media_id}/stream")
    assert stream_res.status_code == 200
    assert len(stream_res.content) == len(sample_video_bytes)

    # 6. Stream video (HTTP Range: standard start-end)
    range_res = client.get(f"/api/v1/media/{media_id}/stream", headers={"Range": "bytes=0-49"})
    assert range_res.status_code == 206
    assert len(range_res.content) == 50
    assert "bytes 0-49/" in range_res.headers.get("Content-Range", "")

    # 7. Stream video (HTTP Range: suffix range, e.g. last 40 bytes)
    suffix_res = client.get(f"/api/v1/media/{media_id}/stream", headers={"Range": "bytes=-40"})
    assert suffix_res.status_code == 206
    assert len(suffix_res.content) == 40
    assert suffix_res.content == sample_video_bytes[-40:]

    # 8. Stream video (HTTP Range: out of bounds range -> HTTP 416)
    oob_res = client.get(f"/api/v1/media/{media_id}/stream", headers={"Range": "bytes=999999-"})
    assert oob_res.status_code == 416
    assert "bytes */" in oob_res.headers.get("Content-Range", "")

    # 9. Stream video (HTTP Range: malformed range -> HTTP 416)
    bad_range = client.get(f"/api/v1/media/{media_id}/stream", headers={"Range": "bytes=bad-range"})
    assert bad_range.status_code == 416

    # 10. Duplicate upload detection (must return 409 Conflict)
    dup_files = {"file": ("test_presentation_copy.mp4", io.BytesIO(sample_video_bytes), "video/mp4")}
    dup_res = client.post("/api/v1/media/upload", files=dup_files)
    assert dup_res.status_code == 409
    assert dup_res.json()["error_code"] == "DUPLICATE_MEDIA"

    # 11. Invalid extension upload (must return 400 Bad Request)
    bad_files = {"file": ("malicious.exe", io.BytesIO(b"bad binary"), "application/x-msdownload")}
    bad_res = client.post("/api/v1/media/upload", files=bad_files)
    assert bad_res.status_code == 400
    assert bad_res.json()["error_code"] == "INVALID_MEDIA_FILE"

    # 12. Delete media
    del_res = client.delete(f"/api/v1/media/{media_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 13. Verify deleted
    get_after_del = client.get(f"/api/v1/media/{media_id}")
    assert get_after_del.status_code == 404
