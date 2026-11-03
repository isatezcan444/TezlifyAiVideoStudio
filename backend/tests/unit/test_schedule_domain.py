import pytest
from datetime import datetime, timezone, timedelta
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    InvalidScheduleStateTransitionException,
    InvalidScheduleTimeException,
    ScheduleDomainException,
)

def test_scheduled_publish_creation_and_utc_normalization():
    now_utc = datetime.now(timezone.utc)
    future = now_utc + timedelta(hours=2)

    item = ScheduledPublish(
        id="sched_1",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Test Animation Video",
        scheduled_at_utc=future,
        platform=SocialPlatform.YOUTUBE,
        timezone="Europe/Istanbul",
    )

    assert item.id == "sched_1"
    assert item.status == ScheduleStatus.SCHEDULED
    assert item.scheduled_at_utc.tzinfo == timezone.utc
    assert item.version == 1
    assert item.attempt_count == 0
    assert item.max_attempts == 3

def test_naive_datetime_raises_exception():
    naive = datetime(2026, 12, 1, 12, 0, 0)
    with pytest.raises(InvalidScheduleTimeException):
        ScheduledPublish(
            id="sched_2",
            media_asset_id="media_1",
            social_account_id="acc_1",
            title="Naive Time",
            scheduled_at_utc=naive,
        )

def test_valid_state_transitions():
    now_utc = datetime.now(timezone.utc)
    item = ScheduledPublish(
        id="sched_3",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Transitions",
        scheduled_at_utc=now_utc + timedelta(hours=1),
    )

    # SCHEDULED -> PROCESSING
    item.mark_processing()
    assert item.status == ScheduleStatus.PROCESSING
    assert item.attempt_count == 1
    assert item.started_at is not None
    assert item.version == 2

    # PROCESSING -> PUBLISHED
    item.mark_published("pub_record_123")
    assert item.status == ScheduleStatus.PUBLISHED
    assert item.publish_record_id == "pub_record_123"
    assert item.completed_at is not None
    assert item.version == 3

    # PUBLISHED is terminal; cannot transition to anything
    with pytest.raises(InvalidScheduleStateTransitionException):
        item.transition_to(ScheduleStatus.SCHEDULED)

def test_invalid_state_transitions():
    now_utc = datetime.now(timezone.utc)
    item = ScheduledPublish(
        id="sched_4",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Invalid Transitions",
        scheduled_at_utc=now_utc + timedelta(hours=1),
    )

    # SCHEDULED cannot directly go to PUBLISHED without PROCESSING
    with pytest.raises(InvalidScheduleStateTransitionException):
        item.transition_to(ScheduleStatus.PUBLISHED)

def test_reschedule_validations():
    now_utc = datetime.now(timezone.utc)
    item = ScheduledPublish(
        id="sched_5",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Reschedule Test",
        scheduled_at_utc=now_utc + timedelta(hours=2),
    )

    # Rescheduling to past should raise InvalidScheduleTimeException
    past = now_utc - timedelta(hours=1)
    with pytest.raises(InvalidScheduleTimeException):
        item.reschedule(new_scheduled_at_utc=past)

    # Rescheduling to future is valid
    new_future = now_utc + timedelta(days=1)
    item.reschedule(new_scheduled_at_utc=new_future, new_timezone="America/New_York")
    assert item.scheduled_at_utc == new_future
    assert item.timezone == "America/New_York"
    assert item.version == 2

def test_cancel_schedule():
    now_utc = datetime.now(timezone.utc)
    item = ScheduledPublish(
        id="sched_6",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Cancel Test",
        scheduled_at_utc=now_utc + timedelta(hours=1),
    )

    item.cancel()
    assert item.status == ScheduleStatus.CANCELLED

    # Cancelled cannot be rescheduled
    with pytest.raises(InvalidScheduleStateTransitionException):
        item.reschedule(new_scheduled_at_utc=now_utc + timedelta(days=2))

def test_is_due_and_can_retry():
    now_utc = datetime.now(timezone.utc)
    past = now_utc - timedelta(minutes=5)
    future = now_utc + timedelta(minutes=10)

    due_item = ScheduledPublish(
        id="sched_due",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Due Item",
        scheduled_at_utc=past,
    )
    assert due_item.is_due(now_utc) is True

    future_item = ScheduledPublish(
        id="sched_future",
        media_asset_id="media_1",
        social_account_id="acc_1",
        title="Future Item",
        scheduled_at_utc=future,
    )
    assert future_item.is_due(now_utc) is False

    # Retry checks
    due_item.mark_failed("ERROR_CODE", "Some error")
    assert due_item.can_retry() is True
    due_item.attempt_count = 3
    assert due_item.can_retry() is False
