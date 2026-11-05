import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional

from tezlify_studio.infrastructure.persistence.database import SessionLocal
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
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.infrastructure.persistence.models.publish_models import SocialAccountModel
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
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
from tezlify_studio.domain.exceptions.publish_exceptions import QuotaExceededException
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.infrastructure.scheduler.scheduler_service import PublishSchedulerService

class FakeStorage(MediaStoragePort):
    def exists(self, path: str) -> bool:
        return True
    def get_file_size(self, path: str) -> int:
        return 5000
    def save_stream(self, stream, destination_filename, chunk_size=1048576, max_bytes=None):
        return ("/tmp/fake.mp4", 5000, "fake_sha256")
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
                channel_name="Scheduler Channel",
            ),
            connection=PlatformConnection(
                id=connection_id,
                platform=SocialPlatform.YOUTUBE,
                account_external_id="google_sched",
                account_display_name="Scheduler Account",
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
            access_token="access_sched",
        )


class FakeSchedulerPublisher(YouTubePublisherPort):
    def __init__(self):
        self.should_fail_quota = False
        self.should_fail_transient = False

    def generate_auth_url(self, state: str, code_challenge: str, redirect_uri: Optional[str] = None) -> str:
        return ""
    def exchange_code_for_tokens(self, *args, **kwargs) -> Dict[str, Any]:
        return {}
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {"access_token": "refreshed_token", "expires_in": 3600}
    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        return {"channel_id": "UC_TEST", "channel_title": "Test Channel"}
    def initiate_resumable_upload(self, *args, **kwargs) -> str:
        if self.should_fail_quota:
            raise QuotaExceededException("Quota exhausted")
        if self.should_fail_transient:
            raise ConnectionError("Network glitch")
        return "https://upload.example.com/session_worker"
    def upload_chunk(self, *args, **kwargs) -> Tuple[int, Optional[Dict[str, Any]]]:
        if self.should_fail_transient:
            raise ConnectionError("Chunk network error")
        return 200, {"id": "mock_yt_scheduled_1"}
    def query_upload_status(self, *args, **kwargs) -> int:
        return 0
    def upload_custom_thumbnail(self, *args, **kwargs) -> bool:
        return True

def setup_test_prerequisites(db):
    # Clear any leftover active youtube accounts so our test account is the primary active one
    db.query(SocialAccountModel).filter(SocialAccountModel.platform == SocialPlatform.YOUTUBE.value).delete()
    db.commit()

    media_repo = MediaRepositoryImpl(db)
    account_repo = SocialAccountRepositoryImpl(db)

    media_id = f"m_{uuid.uuid4().hex[:8]}"
    acc_id = f"acc_{uuid.uuid4().hex[:8]}"
    file_path = f"/tmp/test_{media_id}.mp4"
    with open(file_path, "wb") as f:
        f.write(b"0" * 5000)

    media = MediaAsset(
        id=media_id,
        filename=f"test_{media_id}.mp4",
        original_filename=f"test_{media_id}.mp4",
        file_path=file_path,
        file_size_bytes=5000,
        mime_type="video/mp4",
        sha256_hash=f"hash_{uuid.uuid4().hex}",
        status=MediaStatus.READY,
    )
    media_repo.save(media)

    account = SocialAccount(
        id=acc_id,
        platform=SocialPlatform.YOUTUBE,
        account_name="Scheduler Channel",
        channel_id=f"UC_{acc_id}",
        is_active=True,
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    account_repo.save(account)

    token_storage = InMemoryTokenStorageAdapter()
    token_storage.store_tokens(acc_id, "access_sched", "refresh_sched")

    connection_repo = PlatformConnectionRepositoryImpl(db)
    channel_repo = PlatformChannelRepositoryImpl(db)
    connection_id = f"conn_{acc_id}"
    channel_id = f"ch_{acc_id}"
    connection_repo.save(
        PlatformConnection(
            id=connection_id,
            platform=SocialPlatform.YOUTUBE,
            account_external_id=f"google_{acc_id}",
            account_display_name="Scheduler Account",
        )
    )
    channel_repo.save(
        PlatformChannel(
            id=channel_id,
            platform_connection_id=connection_id,
            platform=SocialPlatform.YOUTUBE,
            channel_external_id=account.channel_id,
            channel_name="Scheduler Channel",
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
        token_storage,
        cleanup,
        channel_id,
        connection_id,
        account.channel_id,
    )

def test_process_due_scheduled_publish_success():
    db = SessionLocal()
    cleanup = None
    try:
        (
            media_id,
            acc_id,
            token_storage,
            cleanup,
            channel_id,
            connection_id,
            external_channel_id,
        ) = setup_test_prerequisites(db)
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)
        media_repo = MediaRepositoryImpl(db)
        account_repo = SocialAccountRepositoryImpl(db)

        publisher = FakeSchedulerPublisher()
        storage = FakeStorage()

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=media_repo,
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
        )

        sched_id = f"s_{uuid.uuid4().hex[:8]}"
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Due Schedule Job",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
            status=ScheduleStatus.SCHEDULED,
        )
        sched_repo.save(schedule)

        # Process due jobs
        process_use_case = ProcessDueScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            publish_use_case=publish_use_case,
        )
        count = process_use_case.execute()
        assert count == 1

        # Verify schedule is marked PUBLISHED
        saved = sched_repo.get_by_id(sched_id)
        assert saved.status == ScheduleStatus.PUBLISHED
        assert saved.publish_record_id is not None
        assert saved.completed_at is not None

    finally:
        if cleanup:
            cleanup()
        db.close()

def test_process_due_permanent_quota_error():
    db = SessionLocal()
    cleanup = None
    try:
        (
            media_id,
            acc_id,
            token_storage,
            cleanup,
            channel_id,
            connection_id,
            external_channel_id,
        ) = setup_test_prerequisites(db)
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)
        media_repo = MediaRepositoryImpl(db)
        account_repo = SocialAccountRepositoryImpl(db)

        publisher = FakeSchedulerPublisher()
        publisher.should_fail_quota = True
        storage = FakeStorage()

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=media_repo,
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
        )

        sched_id = f"s_quota_{uuid.uuid4().hex[:8]}"
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Quota Fail Job",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=2),
            status=ScheduleStatus.SCHEDULED,
        )
        sched_repo.save(schedule)

        process_use_case = ProcessDueScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            publish_use_case=publish_use_case,
        )
        process_use_case.execute()

        # Quota is permanent; should immediately mark FAILED with no automatic retry
        saved = sched_repo.get_by_id(sched_id)
        assert saved.status == ScheduleStatus.FAILED
        assert saved.last_error_code == "PERMANENT_ERROR"
    finally:
        if cleanup:
            cleanup()
        db.close()

def test_process_due_transient_error_retry_backoff():
    db = SessionLocal()
    cleanup = None
    try:
        (
            media_id,
            acc_id,
            token_storage,
            cleanup,
            channel_id,
            connection_id,
            external_channel_id,
        ) = setup_test_prerequisites(db)
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)
        media_repo = MediaRepositoryImpl(db)
        account_repo = SocialAccountRepositoryImpl(db)

        publisher = FakeSchedulerPublisher()
        publisher.should_fail_transient = True
        storage = FakeStorage()

        publish_use_case = PublishVideoToYouTubeUseCase(
            media_repo=media_repo,
            storage=storage,
            resolver=FakeResolver(channel_id, connection_id, external_channel_id),
            access_provider=FakeAccessProvider(),
            publish_repo=pub_repo,
            publisher=publisher,
        )

        sched_id = f"s_retry_{uuid.uuid4().hex[:8]}"
        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Transient Retry Job",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
            status=ScheduleStatus.SCHEDULED,
            attempt_count=0,
            max_attempts=3,
        )
        sched_repo.save(schedule)

        process_use_case = ProcessDueScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            publish_use_case=publish_use_case,
            retry_delay_minutes=5,
        )
        process_use_case.execute()

        # Should be re-armed to SCHEDULED with future backoff time and attempt count = 1
        saved = sched_repo.get_by_id(sched_id)
        assert saved.status == ScheduleStatus.SCHEDULED
        assert saved.attempt_count == 1
        assert saved.scheduled_at_utc > datetime.now(timezone.utc)
    finally:
        if cleanup:
            cleanup()
        db.close()

def test_reconcile_scheduled_publishes_on_reboot():
    db = SessionLocal()
    cleanup = None
    try:
        (
            media_id,
            acc_id,
            _,
            cleanup,
            channel_id,
            connection_id,
            external_channel_id,
        ) = setup_test_prerequisites(db)
        sched_repo = ScheduledPublishRepositoryImpl(db)
        pub_repo = PublishRecordRepositoryImpl(db)

        # 1. Zombie PROCESSING task
        zombie_id = f"s_zombie_{uuid.uuid4().hex[:8]}"
        zombie = ScheduledPublish(
            id=zombie_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Zombie Task",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=10),
            status=ScheduleStatus.PROCESSING,
        )
        sched_repo.save(zombie)

        # 2. Missed task (scheduled 2 hours ago while offline, grace period 60m)
        missed_id = f"s_missed_{uuid.uuid4().hex[:8]}"
        missed = ScheduledPublish(
            id=missed_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Missed Task",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(hours=2),
            status=ScheduleStatus.SCHEDULED,
        )
        sched_repo.save(missed)

        # 3. Within grace period task (scheduled 10m ago)
        grace_id = f"s_grace_{uuid.uuid4().hex[:8]}"
        grace = ScheduledPublish(
            id=grace_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            channel_id=channel_id,
            platform_connection_id=connection_id,
            channel_attribution="exact",
            title="Grace Task",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=10),
            status=ScheduleStatus.SCHEDULED,
        )
        sched_repo.save(grace)

        reconcile_use_case = ReconcileScheduledPublishesUseCase(
            schedule_repo=sched_repo,
            publish_repo=pub_repo,
            grace_period_minutes=60,
        )
        paused_count, missed_count = reconcile_use_case.execute()

        assert paused_count == 1
        assert missed_count == 1

        # Verify states
        zombie_saved = sched_repo.get_by_id(zombie_id)
        assert zombie_saved.status == ScheduleStatus.PAUSED
        assert zombie_saved.last_error_code == "SERVER_RESTARTED"

        missed_saved = sched_repo.get_by_id(missed_id)
        assert missed_saved.status == ScheduleStatus.MISSED
        assert missed_saved.last_error_code == "MISSED_SCHEDULE"

        grace_saved = sched_repo.get_by_id(grace_id)
        assert grace_saved.status == ScheduleStatus.SCHEDULED  # preserved for next worker tick
    finally:
        if cleanup:
            cleanup()
        db.close()

def test_scheduler_service_lifecycle_and_status():
    storage = FakeStorage()
    token_storage = InMemoryTokenStorageAdapter()
    publisher = FakeSchedulerPublisher()

    service = PublishSchedulerService(
        storage=storage,
        token_storage=token_storage,
        youtube_publisher=publisher,
        check_interval_seconds=1,
    )

    try:
        assert service.is_running() is False
        service.start()
        assert service.is_running() is True

        status = service.get_status()
        assert status.is_running is True
        assert status.check_interval_seconds == 1
    finally:
        service.stop()
        assert service.is_running() is False
