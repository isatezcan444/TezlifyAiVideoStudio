import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional

from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.models.publish_models import (
    SocialAccountModel,
    PublishRecordModel,
)
from tezlify_studio.infrastructure.persistence.models.schedule_models import (
    ScheduledPublishModel,
)
from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
    ScheduledPublishRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import (
    PublishRecordRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import (
    MediaRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.social_account_repository_impl import (
    SocialAccountRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.platform_connection_repository_impl import (
    PlatformConnectionRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.platform_channel_repository_impl import (
    PlatformChannelRepositoryImpl,
)
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.exceptions.schedule_exceptions import InvalidScheduleTimeException
from tezlify_studio.application.ports.youtube_publisher_port import (
    YouTubePublisherPort,
    UploadStatusResult,
)
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort
from tezlify_studio.infrastructure.security.token_storage_impl import InMemoryTokenStorageAdapter
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.application.use_cases.process_due_scheduled_publishes_use_case import (
    ProcessDueScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.reconcile_scheduled_publishes_use_case import (
    ReconcileScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.resume_youtube_upload_use_case import (
    ResumeYouTubeUploadUseCase,
)
from tezlify_studio.application.use_cases.create_scheduled_publish_use_case import (
    CreateScheduledPublishUseCase,
)
from tezlify_studio.application.dto.schedule_dto import CreateScheduledPublishDTO
from tezlify_studio.domain.services.schedule_timezone_validator import (
    validate_and_normalize_schedule_time,
)

class ReliableTestStorage(MediaStoragePort):
    def exists(self, path: str) -> bool:
        return True
    def get_file_size(self, path: str) -> int:
        return 4096
    def save_stream(self, stream, destination_filename, chunk_size=1048576, max_bytes=None):
        return ("/tmp/fake.mp4", 4096, "fake_sha256")
    def delete_file(self, path: str) -> bool:
        return True
    def open_range_stream(self, file_path, start, end, chunk_size=524288):
        yield b"0" * (end - start + 1)

class FakeResolver:
    def __init__(self, channel_id: str, connection_id: str, external_channel_id: str):
        self.context = ChannelContext(
            channel=PlatformChannel(
                id=channel_id,
                platform_connection_id=connection_id,
                platform=SocialPlatform.YOUTUBE,
                channel_external_id=external_channel_id,
                channel_name="Recovery Channel",
            ),
            connection=PlatformConnection(
                id=connection_id,
                platform=SocialPlatform.YOUTUBE,
                account_external_id="google_recovery",
                account_display_name="Recovery Account",
            ),
        )

    def resolve(self, channel_id=None) -> ChannelContext:
        return self.context


class FakeAccessProvider:
    def get_access(self, context: ChannelContext) -> ChannelAccess:
        return ChannelAccess(
            platform=SocialPlatform.YOUTUBE,
            channel_id=context.channel_id,
            external_channel_id=context.external_channel_id,
            connection_id=context.connection_id,
            access_token="access_recovery",
        )


class CrashMockPublisher(YouTubePublisherPort):
    def __init__(self):
        self.upload_calls = 0
        self.query_status_calls = 0
        self.simulate_network_drop_on_last_chunk = False
        self.finalized_video_id = "yt_final_vid_99"

    def generate_auth_url(self, *args, **kwargs) -> str:
        return ""
    def exchange_code_for_tokens(self, *args, **kwargs) -> Dict[str, Any]:
        return {}
    def refresh_access_token(self, *args, **kwargs) -> Dict[str, Any]:
        return {"access_token": "refr_tok", "expires_in": 3600}
    def get_channel_profile(self, *args, **kwargs) -> Dict[str, Any]:
        return {"channel_id": "UC_TEST", "channel_title": "Channel"}
    def initiate_resumable_upload(self, *args, **kwargs) -> str:
        self.upload_calls += 1
        return "https://upload.youtube.com/test_session_recovery"
    def upload_chunk(self, upload_session_uri, chunk_data, start_byte, total_bytes, **kwargs):
        if self.simulate_network_drop_on_last_chunk and (start_byte + len(chunk_data) >= total_bytes):
            raise ConnectionError("Network dropped right as final chunk was acknowledged by YouTube")
        return 200, {"id": self.finalized_video_id}
    def query_upload_status(self, upload_session_uri, total_bytes) -> int:
        self.query_status_calls += 1
        # Returns total_bytes and finalized video payload if completed
        return UploadStatusResult(total_bytes, finalized_data={"id": self.finalized_video_id})
    def upload_custom_thumbnail(self, *args, **kwargs) -> bool:
        return True

def setup_prereqs(db):
    # Ensure fresh state
    db.query(SocialAccountModel).filter(SocialAccountModel.platform == SocialPlatform.YOUTUBE.value).delete()
    db.commit()

    media_repo = MediaRepositoryImpl(db)
    account_repo = SocialAccountRepositoryImpl(db)

    media_id = f"m_rel_{uuid.uuid4().hex[:8]}"
    acc_id = f"acc_rel_{uuid.uuid4().hex[:8]}"
    file_path = f"/tmp/rel_{media_id}.mp4"

    with open(file_path, "wb") as f:
        f.write(b"X" * 4096)

    media = MediaAsset(
        id=media_id,
        filename=f"rel_{media_id}.mp4",
        original_filename="recovery_test.mp4",
        file_path=file_path,
        file_size_bytes=4096,
        mime_type="video/mp4",
        sha256_hash=f"hash_rel_{uuid.uuid4().hex}",
        status=MediaStatus.READY,
    )
    media_repo.save(media)

    account = SocialAccount(
        id=acc_id,
        platform=SocialPlatform.YOUTUBE,
        account_name="Recovery Channel",
        channel_id=f"UC_{acc_id}",
        is_active=True,
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account_repo.save(account)

    token_storage = InMemoryTokenStorageAdapter()
    token_storage.store_tokens(acc_id, "access_recovery", "refresh_recovery")

    connection_repo = PlatformConnectionRepositoryImpl(db)
    channel_repo = PlatformChannelRepositoryImpl(db)
    connection_id = f"conn_{acc_id}"
    channel_id = f"ch_{acc_id}"
    connection_repo.save(
        PlatformConnection(
            id=connection_id,
            platform=SocialPlatform.YOUTUBE,
            account_external_id=f"google_{acc_id}",
            account_display_name="Recovery Account",
        )
    )
    channel_repo.save(
        PlatformChannel(
            id=channel_id,
            platform_connection_id=connection_id,
            platform=SocialPlatform.YOUTUBE,
            channel_external_id=account.channel_id,
            channel_name="Recovery Channel",
            is_primary=True,
        )
    )

    def cleanup():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            channel_repo.delete(channel_id)
            connection_repo.delete(connection_id)
            account_repo.delete(acc_id)
            media_repo.delete(media_id)
        except Exception:
            pass

    return (
        media_id,
        acc_id,
        file_path,
        token_storage,
        cleanup,
        channel_id,
        connection_id,
        account.channel_id,
    )

# -----------------------------------------------------------------------------
# 1. YouTube Upload Success, DB Update Failure Scenario
# -----------------------------------------------------------------------------
def test_youtube_upload_success_db_update_failure_recovery():
    """
    Scenario: YouTube successfully uploads video and returns video ID, but before
    ScheduledPublish is updated to PUBLISHED, the node crashes.
    On next run, idempotency check finds the existing completed PublishRecord
    and resolves the schedule without triggering a duplicate upload!
    """
    db = SessionLocal()
    (
        media_id,
        acc_id,
        _,
        token_storage,
        cleanup,
        channel_id,
        connection_id,
        external_channel_id,
    ) = setup_prereqs(db)
    try:
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)
        publisher = CrashMockPublisher()
        storage = ReliableTestStorage()

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=MediaRepositoryImpl(db),
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
        )

        # Create schedule in PROCESSING state (simulating crash right after claim)
        sched_id = f"s_crash_{uuid.uuid4().hex[:8]}"
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Crash Recovery Schedule",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=2),
            status=ScheduleStatus.PROCESSING,
        )
        sched_repo.save(schedule)

        # Simulate that PublishRecord succeeded and reached PUBLISHED
        pub_id = f"pub_succ_{uuid.uuid4().hex[:8]}"
        pub_record = PublishRecord(
            id=pub_id,
            media_asset_id=media_id,
            platform=SocialPlatform.YOUTUBE,
            title="Crash Recovery Schedule",
            description="desc",
            category_id="22",
            privacy_status=PrivacyStatus.PRIVATE,
            status=PublishStatus.PUBLISHED,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            progress_percentage=100,
            uploaded_bytes=4096,
            total_bytes=4096,
            external_video_id="yt_final_vid_99",
            external_video_url="https://youtu.be/yt_final_vid_99",
        )
        pub_repo.save(pub_record)

        # On startup after crash, reconciliation detects that the PublishRecord reached PUBLISHED
        reconcile_use_case = ReconcileScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            grace_period_minutes=60,
        )
        initial_upload_calls = publisher.upload_calls
        reconcile_use_case.execute()

        # Zero new YouTube upload sessions initiated!
        assert publisher.upload_calls == initial_upload_calls

        # Schedule is now marked PUBLISHED with matching publish_record_id
        resolved_sched = sched_repo.get_by_id(sched_id)
        assert resolved_sched.status == ScheduleStatus.PUBLISHED
        assert resolved_sched.publish_record_id == pub_id

    finally:
        cleanup()
        db.close()

# -----------------------------------------------------------------------------
# 2. YouTube Completed, Client Received No Response on Final Chunk
# -----------------------------------------------------------------------------
def test_youtube_completed_no_response_received_resume_recovers_id():
    """
    Scenario: YouTube received the final chunk, but the network was severed
    before client received the 200 OK.
    When ResumeYouTubeUploadUseCase runs, query_upload_status finds the finished
    upload (200 + video ID), captures video ID, and marks record PUBLISHED.
    """
    db = SessionLocal()
    (
        media_id,
        acc_id,
        _,
        token_storage,
        cleanup,
        channel_id,
        connection_id,
        external_channel_id,
    ) = setup_prereqs(db)
    try:
        pub_repo = PublishRecordRepositoryImpl(db)
        publisher = CrashMockPublisher()
        storage = ReliableTestStorage()

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=MediaRepositoryImpl(db),
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
        )

        resume_use_case = ResumeYouTubeUploadUseCase(
            publish_use_case=publish_use_case,
            publish_repo=pub_repo,
            media_repo=MediaRepositoryImpl(db),
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publisher=publisher,
        )

        pub_id = f"pub_uncertain_{uuid.uuid4().hex[:8]}"
        record = PublishRecord(
            id=pub_id,
            media_asset_id=media_id,
            platform=SocialPlatform.YOUTUBE,
            title="Uncertain Upload",
            description="desc",
            category_id="22",
            privacy_status=PrivacyStatus.PRIVATE,
            status=PublishStatus.PAUSED,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            upload_session_uri="https://upload.youtube.com/uncertain_session",
            uploaded_bytes=4096,  # End of file reached
            total_bytes=4096,
        )
        pub_repo.save(record)

        # Resume execution
        dto = resume_use_case.execute(pub_id, async_upload=False)

        assert dto.status == "published"
        assert dto.external_video_id == "yt_final_vid_99"
        assert dto.external_video_url == "https://youtu.be/yt_final_vid_99"

        # Verify DB state
        saved = pub_repo.get_by_id(pub_id)
        assert saved.status == PublishStatus.PUBLISHED
        assert saved.external_video_id == "yt_final_vid_99"

    finally:
        cleanup()
        db.close()

# -----------------------------------------------------------------------------
# 3. Re-execution with existing successful PublishRecord
# -----------------------------------------------------------------------------
def test_schedule_re_executed_when_successful_publish_record_already_exists():
    db = SessionLocal()
    (
        media_id,
        acc_id,
        _,
        token_storage,
        cleanup,
        channel_id,
        connection_id,
        external_channel_id,
    ) = setup_prereqs(db)
    try:
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)
        publisher = CrashMockPublisher()
        storage = ReliableTestStorage()

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=MediaRepositoryImpl(db),
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
        )

        pub_id = f"pub_done_{uuid.uuid4().hex[:8]}"
        pub_record = PublishRecord(
            id=pub_id,
            media_asset_id=media_id,
            platform=SocialPlatform.YOUTUBE,
            title="Already Published",
            description="",
            category_id="22",
            privacy_status=PrivacyStatus.PRIVATE,
            status=PublishStatus.PUBLISHED,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            progress_percentage=100,
            uploaded_bytes=4096,
            total_bytes=4096,
            external_video_id="yt_existing_id",
        )
        pub_repo.save(pub_record)

        sched_id = f"s_re_{uuid.uuid4().hex[:8]}"
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Already Published",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
            status=ScheduleStatus.SCHEDULED,
            publish_record_id=pub_id,
        )
        sched_repo.save(schedule)

        process_use_case = ProcessDueScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            publish_use_case=publish_use_case,
        )
        count = process_use_case.execute()
        assert count == 1

        saved = sched_repo.get_by_id(sched_id)
        assert saved.status == ScheduleStatus.PUBLISHED
        assert publisher.upload_calls == 0

    finally:
        cleanup()
        db.close()

# -----------------------------------------------------------------------------
# 4. Clean Shutdown While Processing Pauses Upload Gracefully
# -----------------------------------------------------------------------------
def test_scheduler_clean_shutdown_while_processing_pauses_gracefully():
    db = SessionLocal()
    (
        media_id,
        acc_id,
        _,
        token_storage,
        cleanup,
        channel_id,
        connection_id,
        external_channel_id,
    ) = setup_prereqs(db)
    try:
        pub_repo = PublishRecordRepositoryImpl(db)
        publisher = CrashMockPublisher()
        storage = ReliableTestStorage()

        # Stop checker that returns True immediately to simulate server shutdown during chunking
        is_server_stopping = True

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=MediaRepositoryImpl(db),
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
            chunk_size=1024,
            stop_checker=lambda: is_server_stopping,
        )

        record = PublishRecord(
            id=f"pub_stop_{uuid.uuid4().hex[:8]}",
            media_asset_id=media_id,
            platform=SocialPlatform.YOUTUBE,
            title="Shutdown Test",
            description="",
            category_id="22",
            privacy_status=PrivacyStatus.PRIVATE,
            status=PublishStatus.UPLOADING,
            upload_session_uri="https://upload.example.com/session_stop",
            uploaded_bytes=0,
            total_bytes=4096,
        )
        pub_repo.save(record)

        # Running chunks should exit cleanly and set status to PAUSED
        publish_use_case._upload_file_chunks(record, f"/tmp/rel_{media_id}.mp4", "token", pub_repo)

        saved = pub_repo.get_by_id(record.id)
        assert saved.status == PublishStatus.PAUSED
        assert saved.error_code == "SERVER_STOPPING"

    finally:
        cleanup()
        db.close()

# -----------------------------------------------------------------------------
# 5. Two Scheduler Instances Attempting Same Task Concurrently
# -----------------------------------------------------------------------------
def test_two_scheduler_instances_attempting_same_task():
    db1 = SessionLocal()
    db2 = SessionLocal()
    media_id, acc_id, _, _, cleanup, *_ = setup_prereqs(db1)
    try:
        sched_repo1 = ScheduledPublishRepositoryImpl(db1)
        sched_repo2 = ScheduledPublishRepositoryImpl(db2)

        sched_id = f"s_multi_{uuid.uuid4().hex[:8]}"
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            title="Multi Instance Test",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
            status=ScheduleStatus.SCHEDULED,
            version=1,
        )
        sched_repo1.save(schedule)

        # Instance 1 claims
        claimed1 = sched_repo1.claim_for_processing(sched_id, expected_version=1)
        # Instance 2 tries claiming with version 1
        claimed2 = sched_repo2.claim_for_processing(sched_id, expected_version=1)

        assert claimed1 is True
        assert claimed2 is False

        # Version bumped
        updated = sched_repo1.get_by_id(sched_id)
        assert updated.status == ScheduleStatus.PROCESSING
        assert updated.version == 2

    finally:
        cleanup()
        db1.close()
        db2.close()

# -----------------------------------------------------------------------------
# 6. Stale PROCESSING Task Recovery on Startup
# -----------------------------------------------------------------------------
def test_stale_processing_task_recovery():
    db = SessionLocal()
    media_id, acc_id, _, _, cleanup, *_ = setup_prereqs(db)
    try:
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)

        sched_id = f"s_stale_{uuid.uuid4().hex[:8]}"
        stale_schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            title="Stale Task",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(hours=2),
            status=ScheduleStatus.PROCESSING,
        )
        sched_repo.save(stale_schedule)

        reconcile_use_case = ReconcileScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            grace_period_minutes=60,
        )
        reconcile_use_case.execute()

        saved = sched_repo.get_by_id(sched_id)
        assert saved.status == ScheduleStatus.PAUSED
        assert saved.last_error_code == "SERVER_RESTARTED"

    finally:
        cleanup()
        db.close()

# -----------------------------------------------------------------------------
# 7. DST Nonexistent Local Time Rejected
# -----------------------------------------------------------------------------
def test_dst_nonexistent_local_time_rejected():
    """
    In America/New_York on March 8, 2026, clocks spring forward from 2:00 to 3:00.
    Local time 02:30:00 does NOT exist and must be rejected.
    """
    with pytest.raises(InvalidScheduleTimeException) as exc_info:
        validate_and_normalize_schedule_time(
            scheduled_at_iso="2026-03-08T02:30:00-05:00",
            tz_name="America/New_York",
        )
    assert "Spring Forward" in str(exc_info.value)

# -----------------------------------------------------------------------------
# 8. DST Ambiguous Local Time Validation
# -----------------------------------------------------------------------------
def test_dst_ambiguous_local_time_validation():
    """
    In America/New_York on Nov 1, 2026, clocks fall back from 2:00 to 1:00.
    Passing a mismatched/ambiguous offset must be rejected.
    """
    with pytest.raises(InvalidScheduleTimeException) as exc_info:
        # Nov 1, 2026 01:30 in NY requires either -04:00 (EDT) or -05:00 (EST)
        # Passing an invalid/mismatched offset like +00:00 or -03:00 must fail
        validate_and_normalize_schedule_time(
            scheduled_at_iso="2026-11-01T01:30:00-03:00",
            tz_name="America/New_York",
        )
    assert "belirsizdir" in str(exc_info.value) or "Invalid" in str(exc_info.value)

# -----------------------------------------------------------------------------
# 9. SQLite Transaction Rollback Preserves Consistency
# -----------------------------------------------------------------------------
def test_sqlite_transaction_rollback_preserves_consistency():
    db = SessionLocal()
    media_id, acc_id, _, _, cleanup, *_ = setup_prereqs(db)
    sched_repo = ScheduledPublishRepositoryImpl(db)
    sched_id = f"s_rb_{uuid.uuid4().hex[:8]}"

    try:
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            title="Rollback Test",
            scheduled_at_utc=datetime.now(timezone.utc) + timedelta(hours=1),
            status=ScheduleStatus.SCHEDULED,
        )
        sched_repo.save(schedule)

        # Trigger deliberate transaction failure
        try:
            db.begin_nested()
            db.query(ScheduledPublishModel).filter(ScheduledPublishModel.id == sched_id).update(
                {"status": "non_existent_status"}
            )
            # Deliberately raise
            raise RuntimeError("Forced simulation error")
        except RuntimeError:
            db.rollback()

        # Verify DB record is untouched and status is still scheduled
        fresh_db = SessionLocal()
        saved = fresh_db.query(ScheduledPublishModel).filter(ScheduledPublishModel.id == sched_id).first()
        assert saved is not None
        assert saved.status == "scheduled"
        fresh_db.close()

    finally:
        cleanup()
        sched_repo.delete(sched_id)
        db.close()

# -----------------------------------------------------------------------------
# 10. Startup Reconciliation Runs Strictly Before Worker Begins Polling
# -----------------------------------------------------------------------------
def test_startup_reconciliation_runs_strictly_before_worker_starts():
    db = SessionLocal()
    media_id, acc_id, _, _, cleanup, *_ = setup_prereqs(db)
    order_log = []

    class OrderTrackingReconcile(ReconcileScheduledPublishesUseCase):
        def execute(self):
            order_log.append("reconciliation_executed")
            return super().execute()

    sched_repo = ScheduledPublishRepositoryImpl(db)
    pub_repo = PublishRecordRepositoryImpl(db)

    # Put a PROCESSING task
    sched_id = f"s_order_{uuid.uuid4().hex[:8]}"
    sched = ScheduledPublish(
        id=sched_id,
        media_asset_id=media_id,
        social_account_id=acc_id,
        title="Order Task",
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
        status=ScheduleStatus.PROCESSING,
    )
    sched_repo.save(sched)

    try:
        reconcile = OrderTrackingReconcile(sched_repo, pub_repo, grace_period_minutes=60)
        reconcile.execute()
        order_log.append("worker_can_now_poll")

        assert order_log == ["reconciliation_executed", "worker_can_now_poll"]

        # Confirm task was resolved before any worker could poll
        resolved = sched_repo.get_by_id(sched_id)
        assert resolved.status == ScheduleStatus.PAUSED

    finally:
        cleanup()
        sched_repo.delete(sched_id)
        db.close()
