import io
import uuid
import pytest
import httpx
from typing import Dict, Any, List, Tuple, Optional
from fastapi.testclient import TestClient

from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies.container import (
    get_youtube_publisher,
    get_token_storage,
)
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.infrastructure.security.token_storage_impl import InMemoryTokenStorageAdapter
from tezlify_studio.domain.exceptions.publish_exceptions import (
    UploadSessionExpiredException,
    QuotaExceededException,
    PublishDomainException,
)
from tezlify_studio.infrastructure.media.youtube_api_client_impl import YouTubeApiClientImpl
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YOUTUBE_SCOPES
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import (
    PublishRecordRepositoryImpl,
)
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.application.use_cases.reconcile_publish_records_use_case import (
    ReconcilePublishRecordsUseCase,
)

class MockResiliencePublisher(YouTubePublisherPort):
    def __init__(self):
        self.should_fail_session_expired = False
        self.should_fail_quota = False
        self.query_return_bytes = 0

    def generate_auth_url(
        self,
        state: str,
        code_challenge: str,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code_for_tokens(self, code: str, code_verifier: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        return {
            "access_token": "token_resilience",
            "refresh_token": "refresh_resilience",
            "expires_in": 3600,
            "scope": " ".join(YOUTUBE_SCOPES),
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {"access_token": "token_new", "expires_in": 3600}

    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        return {"channel_id": "UC_RESILIENCE", "channel_title": "Resilience Channel", "avatar_url": None}

    def initiate_resumable_upload(self, *args, **kwargs) -> str:
        if self.should_fail_quota:
            raise QuotaExceededException("API quota exceeded")
        return "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=resilience_session"

    def upload_chunk(self, upload_session_uri: str, chunk_data: bytes, start_byte: int, total_bytes: int) -> Tuple[int, Optional[Dict[str, Any]]]:
        if self.should_fail_session_expired:
            raise UploadSessionExpiredException("Session 404 expired")
        return 200, {"id": "vid_resilience_1"}

    def query_upload_status(self, upload_session_uri: str, total_bytes: int) -> int:
        if self.should_fail_session_expired:
            raise UploadSessionExpiredException("Session 404 expired on query")
        return self.query_return_bytes

    def upload_custom_thumbnail(self, *args, **kwargs) -> bool:
        return True

resilience_publisher = MockResiliencePublisher()
resilience_storage = InMemoryTokenStorageAdapter()

@pytest.fixture(autouse=True)
def override_resilience_deps():
    app.dependency_overrides[get_youtube_publisher] = lambda: resilience_publisher
    app.dependency_overrides[get_token_storage] = lambda: resilience_storage
    yield
    app.dependency_overrides.pop(get_youtube_publisher, None)
    app.dependency_overrides.pop(get_token_storage, None)

client = TestClient(app)

def test_startup_reconciliation_cleans_zombie_uploads():
    sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 300)
    files = {"file": ("reconcile_sample.mp4", io.BytesIO(sample_bytes), "video/mp4")}
    upload_res = client.post("/api/v1/media/upload", files=files)
    assert upload_res.status_code == 201
    media_id = upload_res.json()["id"]

    db = SessionLocal()
    try:
        repo = PublishRecordRepositoryImpl(db)
        # Create a zombie record stuck in UPLOADING
        zombie_id = f"zombie_{uuid.uuid4().hex[:8]}"
        zombie_record = PublishRecord(
            id=zombie_id,
            media_asset_id=media_id,
            platform=SocialPlatform.YOUTUBE,
            title="Zombie Upload",
            description="Testing crash recovery",
            status=PublishStatus.UPLOADING,
            total_bytes=10000,
            uploaded_bytes=5000,
            upload_session_uri="https://upload.example.com/zombie",
        )
        repo.save(zombie_record)

        # Run reconciliation
        use_case = ReconcilePublishRecordsUseCase(repo)
        reconciled = use_case.execute()

        reconciled_ids = [r.id for r in reconciled]
        assert zombie_id in reconciled_ids

        # Verify DB state has transitioned to PAUSED with SERVER_RESTARTED error_code
        updated = repo.get_by_id(zombie_id)
        assert updated is not None
        assert updated.status == PublishStatus.PAUSED
        assert updated.error_code == "SERVER_RESTARTED"
        assert updated.uploaded_bytes == 5000
    finally:
        db.close()

def test_upload_session_expired_404_resets_and_fails_job():
    import time
    # Connect account
    conn_res = client.post("/api/v1/social/youtube/connect")
    state = conn_res.json()["state"]
    client.get(f"/api/v1/social/youtube/callback?code=mock_code&state={state}")

    # Upload test video
    sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 300)
    files = {"file": ("expired_session.mp4", io.BytesIO(sample_bytes), "video/mp4")}
    upload_res = client.post("/api/v1/media/upload", files=files)
    media_id = upload_res.json()["id"]

    # Trigger publish with expired session simulation
    resilience_publisher.should_fail_session_expired = True
    try:
        payload = {"media_asset_id": media_id, "title": "Session Expired Test"}
        pub_res = client.post("/api/v1/social/youtube/publish", json=payload)
        assert pub_res.status_code == 201

        # Allow async chunk thread to process and fail
        time.sleep(0.3)

        # Verify the record in DB transitioned to FAILED with SESSION_EXPIRED
        db = SessionLocal()
        try:
            repo = PublishRecordRepositoryImpl(db)
            records = repo.list_all(limit=10)
            target = next((r for r in records if r.media_asset_id == media_id), None)
            assert target is not None
            assert target.status == PublishStatus.FAILED
            assert target.error_code == "SESSION_EXPIRED"
            assert target.upload_session_uri is None
            assert target.uploaded_bytes == 0
        finally:
            db.close()
    finally:
        resilience_publisher.should_fail_session_expired = False

def test_api_responses_never_leak_tokens_or_session_uri():
    # Connect and verify
    conn_res = client.post("/api/v1/social/youtube/connect")
    data = conn_res.json()
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert "client_secret" not in data

    # Check status endpoint
    status_res = client.get("/api/v1/social/youtube/status")
    status_data = status_res.json()
    assert "access_token" not in status_data
    assert "refresh_token" not in status_data

    # Check publish listing
    list_res = client.get("/api/v1/social/youtube/publish")
    list_data = list_res.json()
    for item in list_data.get("items", []):
        assert "upload_session_uri" not in item
        assert "access_token" not in item
        assert "refresh_token" not in item

def test_granular_quota_and_forbidden_parsing():
    client_impl = YouTubeApiClientImpl(client_id="test_id")

    # 1. Daily Quota Exceeded (quotaExceeded)
    resp_quota = httpx.Response(
        403,
        json={"error": {"errors": [{"reason": "quotaExceeded"}], "message": "Daily Limit Exceeded"}},
    )
    with pytest.raises(QuotaExceededException):
        client_impl._check_quota_and_forbidden_error(resp_quota)

    # 2. Upload Limit Exceeded (channel daily limit)
    resp_upload_limit = httpx.Response(
        403,
        json={"error": {"errors": [{"reason": "uploadLimitExceeded"}], "message": "The user has exceeded the number of videos they may upload."}},
    )
    with pytest.raises(PublishDomainException) as exc_info:
        client_impl._check_quota_and_forbidden_error(resp_upload_limit)
    assert "günlük video yükleme sınırına" in str(exc_info.value)

    # 3. Access Not Configured (API disabled in console)
    resp_access_cfg = httpx.Response(
        403,
        json={"error": {"errors": [{"reason": "accessNotConfigured"}], "message": "Access Not Configured"}},
    )
    with pytest.raises(PublishDomainException) as exc_info:
        client_impl._check_quota_and_forbidden_error(resp_access_cfg)
    assert "etkinleştirilmemiş" in str(exc_info.value)

    # 4. 308 without Range header returns 0
    resp_308_empty = httpx.Response(308, headers={})
    mock_httpx_client = httpx.Client(transport=httpx.MockTransport(lambda req: resp_308_empty))
    yt_client = YouTubeApiClientImpl(client_id="test_id", client=mock_httpx_client)
    confirmed = yt_client.query_upload_status("https://upload.example.com/test", total_bytes=1000)
    assert confirmed == 0

    # 5. 404 returns UploadSessionExpiredException
    resp_404 = httpx.Response(404)
    mock_404_client = httpx.Client(transport=httpx.MockTransport(lambda req: resp_404))
    yt_404 = YouTubeApiClientImpl(client_id="test_id", client=mock_404_client)
    with pytest.raises(UploadSessionExpiredException):
        yt_404.query_upload_status("https://upload.example.com/test", total_bytes=1000)

def test_5xx_server_error_and_retry_after_backoff():
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call returns 503 with short Retry-After header
            return httpx.Response(503, headers={"Retry-After": "0.01"}, text="Service Unavailable")
        return httpx.Response(308, headers={"Range": "bytes=0-99"})

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    yt = YouTubeApiClientImpl(client_id="test_id", client=mock_client)

    status_code, body = yt.upload_chunk(
        upload_session_uri="https://upload.example.com/chunk",
        chunk_data=b"0" * 100,
        start_byte=0,
        total_bytes=1000,
    )

    assert call_count == 2
    assert status_code == 308
    assert body is None
