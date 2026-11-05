import io
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi.testclient import TestClient

from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies.container import (
    get_youtube_publisher,
    get_token_storage,
)
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.infrastructure.security.token_storage_impl import InMemoryTokenStorageAdapter
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YOUTUBE_SCOPES
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
    ScheduledPublishRepositoryImpl,
)

class ApiFakePublisher(YouTubePublisherPort):
    def generate_auth_url(
        self,
        state: str,
        code_challenge: str,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code_for_tokens(self, *args, **kwargs) -> Dict[str, Any]:
        return {
            "access_token": "api_access_tok",
            "refresh_token": "api_refresh_tok",
            "expires_in": 3600,
            "scope": " ".join(YOUTUBE_SCOPES),
        }

    def refresh_access_token(self, *args, **kwargs) -> Dict[str, Any]:
        return {"access_token": "api_new_tok", "expires_in": 3600}

    def get_channel_profile(self, *args, **kwargs) -> Dict[str, Any]:
        return {"channel_id": "UC_API_SCHED", "channel_title": "Api Schedule Channel"}

    def initiate_resumable_upload(self, *args, **kwargs) -> str:
        return "https://upload.example.com/api_sched"

    def upload_chunk(self, *args, **kwargs):
        return 200, {"id": "yt_sched_api_vid"}

    def query_upload_status(self, *args, **kwargs) -> int:
        return 0

    def upload_custom_thumbnail(self, *args, **kwargs) -> bool:
        return True

api_publisher = ApiFakePublisher()
api_token_storage = InMemoryTokenStorageAdapter()

@pytest.fixture(autouse=True)
def override_api_deps():
    app.dependency_overrides[get_youtube_publisher] = lambda: api_publisher
    app.dependency_overrides[get_token_storage] = lambda: api_token_storage
    yield
    app.dependency_overrides.pop(get_youtube_publisher, None)
    app.dependency_overrides.pop(get_token_storage, None)

client = TestClient(app)

def create_sample_video():
    sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 300)
    files = {"file": ("sched_test_video.mp4", io.BytesIO(sample_bytes), "video/mp4")}
    upload_res = client.post("/api/v1/media/upload", files=files)
    assert upload_res.status_code == 201
    return upload_res.json()["id"]

def connect_youtube_account():
    conn_res = client.post("/api/v1/social/youtube/connect")
    state = conn_res.json()["state"]
    client.get(f"/api/v1/social/youtube/callback?code=mock_code&state={state}")

def test_create_scheduled_publish_and_retrieve():
    connect_youtube_account()
    media_id = create_sample_video()

    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    payload = {
        "media_asset_id": media_id,
        "title": "My Scheduled YouTube Video",
        "description": "Scheduled via Tezlify AI Video Studio",
        "tags": ["animation", "2d", "blender"],
        "privacy_status": "private",
        "scheduled_at": future_time,
        "timezone": "Europe/Istanbul",
    }

    create_res = client.post("/api/v1/scheduler", json=payload)
    assert create_res.status_code == 201
    data = create_res.json()
    sched_id = data["id"]
    assert data["title"] == "My Scheduled YouTube Video"
    assert data["status"] == "scheduled"
    assert data["timezone"] == "Europe/Istanbul"
    assert data["attempt_count"] == 0

    # Retrieve by ID
    get_res = client.get(f"/api/v1/scheduler/{sched_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sched_id

def test_duplicate_schedule_rejected():
    connect_youtube_account()
    media_id = create_sample_video()
    future_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()

    payload = {
        "media_asset_id": media_id,
        "title": "First Schedule",
        "scheduled_at": future_time,
        "timezone": "UTC",
    }
    res1 = client.post("/api/v1/scheduler", json=payload)
    assert res1.status_code == 201

    # Second schedule for same media returns 409
    res2 = client.post("/api/v1/scheduler", json=payload)
    assert res2.status_code == 409
    assert res2.json()["error_code"] == "DUPLICATE_SCHEDULE"

def test_past_date_schedule_rejected():
    connect_youtube_account()
    media_id = create_sample_video()
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    payload = {
        "media_asset_id": media_id,
        "title": "Past Schedule",
        "scheduled_at": past_time,
        "timezone": "UTC",
    }
    res = client.post("/api/v1/scheduler", json=payload)
    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_SCHEDULE_TIME"

def test_naive_datetime_rejected():
    connect_youtube_account()
    media_id = create_sample_video()
    naive_time = "2026-12-01T15:30:00"  # Missing timezone offset

    payload = {
        "media_asset_id": media_id,
        "title": "Naive Time Schedule",
        "scheduled_at": naive_time,
        "timezone": "UTC",
    }
    res = client.post("/api/v1/scheduler", json=payload)
    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_SCHEDULE_TIME"

def test_list_upcoming_and_status_endpoints():
    connect_youtube_account()
    media_id = create_sample_video()
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    payload = {
        "media_asset_id": media_id,
        "title": "Upcoming Video Test",
        "scheduled_at": future_time,
        "timezone": "Europe/London",
    }
    client.post("/api/v1/scheduler", json=payload)

    # List endpoint
    list_res = client.get("/api/v1/scheduler")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert len(list_data["items"]) >= 1

    # Upcoming endpoint
    up_res = client.get("/api/v1/scheduler/upcoming")
    assert up_res.status_code == 200
    assert len(up_res.json()) >= 1

    # Status endpoint
    status_res = client.get("/api/v1/scheduler/status")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert "is_running" in s_data
    assert "active_count" in s_data
    assert s_data["active_count"] >= 1

def test_update_and_cancel_schedule():
    connect_youtube_account()
    media_id = create_sample_video()
    future_time = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()

    payload = {
        "media_asset_id": media_id,
        "title": "Before Update",
        "description": "Original",
        "scheduled_at": future_time,
        "timezone": "UTC",
    }
    create_res = client.post("/api/v1/scheduler", json=payload)
    sched_id = create_res.json()["id"]

    # PATCH update details
    update_payload = {
        "title": "After Update Title",
        "description": "Updated Description",
        "privacy_status": "unlisted",
    }
    patch_res = client.patch(f"/api/v1/scheduler/{sched_id}", json=update_payload)
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "After Update Title"
    assert patch_res.json()["privacy_status"] == "unlisted"

    # DELETE / cancel schedule
    del_res = client.delete(f"/api/v1/scheduler/{sched_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
    assert del_res.json()["item"]["status"] == "cancelled"

def test_retry_failed_schedule():
    connect_youtube_account()
    media_id = create_sample_video()
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    payload = {
        "media_asset_id": media_id,
        "title": "To Fail and Retry",
        "scheduled_at": future_time,
        "timezone": "UTC",
    }
    create_res = client.post("/api/v1/scheduler", json=payload)
    sched_id = create_res.json()["id"]

    # Manually transition to FAILED in DB to simulate failure
    db = SessionLocal()
    try:
        repo = ScheduledPublishRepositoryImpl(db)
        item = repo.get_by_id(sched_id)
        item.mark_processing()
        item.mark_failed("SIMULATED_FAILURE", "Some error occurred")
        repo.save(item)
    finally:
        db.close()

    # Retry endpoint
    new_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    retry_res = client.post(f"/api/v1/scheduler/{sched_id}/retry", json={"scheduled_at": new_time})
    assert retry_res.status_code == 200
    assert retry_res.json()["status"] == "scheduled"
    assert retry_res.json()["last_error_code"] is None
