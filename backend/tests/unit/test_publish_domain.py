import pytest
from datetime import datetime, timezone, timedelta
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.domain.exceptions.publish_exceptions import InvalidPublishStateTransitionException

def test_social_account_token_expiry():
    # Not expired (2 hours ahead)
    valid_acc = SocialAccount(
        id="acc-1",
        platform=SocialPlatform.YOUTUBE,
        account_name="Channel 1",
        channel_id="UC123",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    assert not valid_acc.is_token_expired(buffer_seconds=60)

    # Expired (5 minutes ago)
    expired_acc = SocialAccount(
        id="acc-2",
        platform=SocialPlatform.YOUTUBE,
        account_name="Channel 2",
        channel_id="UC456",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assert expired_acc.is_token_expired(buffer_seconds=60)

    # Within buffer threshold (expires in 30 seconds, buffer 120)
    buff_acc = SocialAccount(
        id="acc-3",
        platform=SocialPlatform.YOUTUBE,
        account_name="Channel 3",
        channel_id="UC789",
        token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    assert buff_acc.is_token_expired(buffer_seconds=120)

def test_publish_record_valid_lifecycle():
    rec = PublishRecord(
        id="pub-1",
        media_asset_id="med-1",
        platform=SocialPlatform.YOUTUBE,
        title="Epic Animation Video",
        total_bytes=1000,
    )
    assert rec.status == PublishStatus.PENDING
    assert rec.progress_percentage == 0

    # PENDING -> UPLOADING
    rec.transition_to(PublishStatus.UPLOADING)
    assert rec.status == PublishStatus.UPLOADING

    # Update progress
    rec.update_progress(uploaded_bytes=500, total_bytes=1000)
    assert rec.progress_percentage == 50

    # Pause and resume
    rec.transition_to(PublishStatus.PAUSED)
    assert rec.status == PublishStatus.PAUSED
    rec.transition_to(PublishStatus.UPLOADING)
    assert rec.status == PublishStatus.UPLOADING

    # UPLOADING -> PUBLISHED
    rec.transition_to(PublishStatus.PUBLISHED)
    assert rec.status == PublishStatus.PUBLISHED
    assert rec.progress_percentage == 100
    assert rec.published_at is not None

def test_publish_record_invalid_transitions():
    rec = PublishRecord(
        id="pub-2",
        media_asset_id="med-2",
        status=PublishStatus.PUBLISHED,
    )
    # PUBLISHED is terminal; cannot transition back to UPLOADING
    with pytest.raises(InvalidPublishStateTransitionException):
        rec.transition_to(PublishStatus.UPLOADING)

    rec_cancelled = PublishRecord(
        id="pub-3",
        media_asset_id="med-3",
        status=PublishStatus.CANCELLED,
    )
    # CANCELLED cannot jump directly to PUBLISHED
    with pytest.raises(InvalidPublishStateTransitionException):
        rec_cancelled.transition_to(PublishStatus.PUBLISHED)

def test_published_transition_to_failed_on_remote_rejection():
    rec = PublishRecord(
        id="pub-remote-fail",
        media_asset_id="med-fail",
        status=PublishStatus.PUBLISHED,
    )
    # PUBLISHED can transition to FAILED when post-verification discovers remote deletion/rejection
    rec.transition_to(
        PublishStatus.FAILED,
        error_code="YOUTUBE_REJECTED",
        error_message="Remote stream processing rejected the video",
    )
    assert rec.status == PublishStatus.FAILED
    assert rec.error_code == "YOUTUBE_REJECTED"
