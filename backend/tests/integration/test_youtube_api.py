import io
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional
from fastapi.testclient import TestClient

from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies.container import (
    get_youtube_publisher,
    get_token_storage,
)
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.infrastructure.security.token_storage_impl import InMemoryTokenStorageAdapter
from tezlify_studio.application.use_cases.oauth_session_store import oauth_session_store

# Fake YouTube Publisher for deterministic integration testing
class FakeYouTubePublisher(YouTubePublisherPort):
    def __init__(self):
        self.chunk_calls = []
        self.initiate_calls = []
        self.pause_chunks = False

    def generate_auth_url(self, state: str, code_challenge: str, redirect_uri: Optional[str] = None) -> str:
        r_uri = redirect_uri or "http://127.0.0.1:8000/api/v1/social/youtube/callback"
        return f"https://accounts.google.com/o/oauth2/v2/auth?client_id=test_client&state={state}&code_challenge={code_challenge}&redirect_uri={r_uri}"

    def exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "access_token": "fake_access_token_123",
            "refresh_token": "fake_refresh_token_456",
            "expires_in": 3600,
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {
            "access_token": "fake_new_access_token_789",
            "expires_in": 3600,
        }

    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        return {
            "channel_id": "UC_TEST_CHANNEL_999",
            "channel_title": "Tezlify Animations Studio",
            "avatar_url": "https://images.example.com/channel_avatar.jpg",
        }

    def initiate_resumable_upload(
        self,
        access_token: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str,
        privacy: str,
        total_bytes: int,
    ) -> str:
        self.initiate_calls.append({"title": title, "total_bytes": total_bytes})
        return "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=session_xyz"

    def upload_chunk(
        self,
        upload_session_uri: str,
        chunk_data: bytes,
        start_byte: int,
        total_bytes: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        self.chunk_calls.append((start_byte, len(chunk_data)))
        if self.pause_chunks:
            return 308, None
        end_byte = start_byte + len(chunk_data)
        if end_byte >= total_bytes:
            # Final chunk completed
            return 200, {"id": "mock_yt_vid_42"}
        return 308, None

    def query_upload_status(self, upload_session_uri: str, total_bytes: int) -> int:
        return 0

    def upload_custom_thumbnail(self, access_token: str, video_id: str, thumbnail_path: str) -> bool:
        return True

fake_publisher = FakeYouTubePublisher()
test_token_storage = InMemoryTokenStorageAdapter()

@pytest.fixture(autouse=True)
def override_youtube_deps():
    app.dependency_overrides[get_youtube_publisher] = lambda: fake_publisher
    app.dependency_overrides[get_token_storage] = lambda: test_token_storage
    yield
    app.dependency_overrides.pop(get_youtube_publisher, None)
    app.dependency_overrides.pop(get_token_storage, None)

client = TestClient(app)

def test_youtube_status_initially_disconnected():
    # Ensure any existing account is purged
    client.delete("/api/v1/social/youtube/disconnect")

    res = client.get("/api/v1/social/youtube/status")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert data["account"] is None

def test_youtube_connect_and_callback_flow():
    # 1. Connect initiates OAuth URL
    connect_res = client.post("/api/v1/social/youtube/connect")
    assert connect_res.status_code == 200
    conn_data = connect_res.json()
    assert "auth_url" in conn_data
    assert "state" in conn_data
    state = conn_data["state"]

    # 2. Callback completes OAuth
    callback_res = client.get(f"/api/v1/social/youtube/callback?code=mock_oauth_code&state={state}")
    assert callback_res.status_code == 200
    assert "text/html" in callback_res.headers["content-type"]
    assert "YouTube Hesabı Başarıyla Bağlandı" in callback_res.text
    assert "Tezlify Animations Studio" in callback_res.text

    # 3. Status is now connected
    status_res = client.get("/api/v1/social/youtube/status")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert st_data["connected"] is True
    assert st_data["account"]["account_name"] == "Tezlify Animations Studio"
    assert st_data["account"]["channel_id"] == "UC_TEST_CHANNEL_999"

def test_youtube_publish_flow_resumable_and_query():
    # 1. Upload a unique media asset
    sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 1024)
    files = {"file": ("publish_test_anim.mp4", io.BytesIO(sample_bytes), "video/mp4")}
    upload_res = client.post("/api/v1/media/upload", files=files)
    assert upload_res.status_code == 201
    media_id = upload_res.json()["id"]

    # 2. Publish video to YouTube
    publish_payload = {
        "media_asset_id": media_id,
        "title": "My Awesome YouTube Animation",
        "description": "Created with Tezlify AI Video Studio",
        "tags": ["animation", "2d", "blender"],
        "category_id": "1",
        "privacy_status": "private",
    }
    pub_res = client.post("/api/v1/social/youtube/publish", json=publish_payload)
    assert pub_res.status_code == 201
    pub_data = pub_res.json()
    publish_id = pub_data["id"]
    assert pub_data["title"] == "My Awesome YouTube Animation"
    assert pub_data["privacy_status"] == "private"

    # 3. Query publish status
    get_res = client.get(f"/api/v1/social/youtube/publish/{publish_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == publish_id

    # 4. List publish jobs
    list_res = client.get("/api/v1/social/youtube/publish")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(item["id"] == publish_id for item in items)

def test_youtube_duplicate_publish_conflict():
    # 1. Ensure YouTube is connected
    conn_res = client.post("/api/v1/social/youtube/connect")
    state = conn_res.json()["state"]
    client.get(f"/api/v1/social/youtube/callback?code=mock_code&state={state}")

    # Set pause_chunks=True so upload stays in UPLOADING state
    fake_publisher.pause_chunks = True
    try:
        sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 500)
        files = {"file": ("dup_test_anim.mp4", io.BytesIO(sample_bytes), "video/mp4")}
        upload_res = client.post("/api/v1/media/upload", files=files)
        media_id = upload_res.json()["id"]

        # First publish succeeds
        payload = {"media_asset_id": media_id, "title": "First Publish"}
        res1 = client.post("/api/v1/social/youtube/publish", json=payload)
        assert res1.status_code == 201

        # Second publish on same media must conflict with 409
        res2 = client.post("/api/v1/social/youtube/publish", json=payload)
        assert res2.status_code == 409
        assert res2.json()["error_code"] == "DUPLICATE_PUBLISH"
    finally:
        fake_publisher.pause_chunks = False

def test_youtube_cancel_publish_job():
    # Connect account
    conn_res = client.post("/api/v1/social/youtube/connect")
    state = conn_res.json()["state"]
    client.get(f"/api/v1/social/youtube/callback?code=mock_code&state={state}")

    fake_publisher.pause_chunks = True
    try:
        sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 500)
        files = {"file": ("cancel_test_anim.mp4", io.BytesIO(sample_bytes), "video/mp4")}
        upload_res = client.post("/api/v1/media/upload", files=files)
        media_id = upload_res.json()["id"]

        # Start publish
        payload = {"media_asset_id": media_id, "title": "Job to Cancel"}
        pub_res = client.post("/api/v1/social/youtube/publish", json=payload)
        publish_id = pub_res.json()["id"]

        # Cancel active job
        cancel_res = client.post(f"/api/v1/social/youtube/publish/{publish_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"
    finally:
        fake_publisher.pause_chunks = False

def test_youtube_disconnect():
    disc_res = client.delete("/api/v1/social/youtube/disconnect")
    assert disc_res.status_code == 200
    assert disc_res.json()["success"] is True

    status_res = client.get("/api/v1/social/youtube/status")
    assert status_res.json()["connected"] is False
