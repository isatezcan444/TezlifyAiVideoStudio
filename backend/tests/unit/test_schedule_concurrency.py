import concurrent.futures
import uuid
from datetime import datetime, timezone, timedelta
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
    ScheduledPublishRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import (
    MediaRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.social_account_repository_impl import (
    SocialAccountRepositoryImpl,
)
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus
from tezlify_studio.domain.enums.media_status import MediaStatus

def test_atomic_claim_concurrency_race_condition():
    db = SessionLocal()
    media_id = f"m_race_{uuid.uuid4().hex[:8]}"
    acc_id = f"acc_race_{uuid.uuid4().hex[:8]}"
    sched_id = f"s_race_{uuid.uuid4().hex[:8]}"

    try:
        # Create prerequisite media asset and account
        media_repo = MediaRepositoryImpl(db)
        account_repo = SocialAccountRepositoryImpl(db)
        sched_repo = ScheduledPublishRepositoryImpl(db)

        media = MediaAsset(
            id=media_id,
            filename=f"race_{media_id}.mp4",
            original_filename="race.mp4",
            file_path=f"/tmp/race_{media_id}.mp4",
            file_size_bytes=1000,
            mime_type="video/mp4",
            sha256_hash=f"hash_race_{uuid.uuid4().hex}",
            status=MediaStatus.READY,
        )
        media_repo.save(media)

        account = SocialAccount(
            id=acc_id,
            platform=SocialPlatform.YOUTUBE,
            account_name="Race Channel",
            channel_id="UC_RACE",
            is_active=True,
        )
        account_repo.save(account)

        schedule = ScheduledPublish(
            id=sched_id,
            media_asset_id=media_id,
            social_account_id=acc_id,
            title="Concurrency Race Test",
            scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
            status=ScheduleStatus.SCHEDULED,
            version=1,
        )
        sched_repo.save(schedule)

        # Launch 10 concurrent threads attempting to claim the exact same schedule at the exact same moment
        num_threads = 10
        claim_results = []

        def attempt_claim():
            thread_db = SessionLocal()
            try:
                repo = ScheduledPublishRepositoryImpl(thread_db)
                return repo.claim_for_processing(schedule_id=sched_id, expected_version=1)
            finally:
                thread_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(attempt_claim) for _ in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                claim_results.append(f.result())

        # Exactly 1 worker must succeed, 9 must fail
        assert claim_results.count(True) == 1
        assert claim_results.count(False) == num_threads - 1

        # Verify DB state is PROCESSING with version bumped to 2
        final_sched = sched_repo.get_by_id(sched_id)
        assert final_sched.status == ScheduleStatus.PROCESSING
        assert final_sched.version == 2
        assert final_sched.attempt_count == 1

    finally:
        try:
            sched_repo.delete(sched_id)
            account_repo.delete(acc_id)
            media_repo.delete(media_id)
        except Exception:
            pass
        db.close()
