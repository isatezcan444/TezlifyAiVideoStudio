from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    InvalidScheduleStateTransitionException,
    InvalidScheduleTimeException,
    ScheduleDomainException,
)

VALID_TRANSITIONS = {
    ScheduleStatus.SCHEDULED: {
        ScheduleStatus.PROCESSING,
        ScheduleStatus.FAILED,
        ScheduleStatus.PAUSED,
        ScheduleStatus.CANCELLED,
        ScheduleStatus.MISSED,
    },
    ScheduleStatus.PROCESSING: {
        ScheduleStatus.PUBLISHED,
        ScheduleStatus.FAILED,
        ScheduleStatus.SCHEDULED,  # for retry backoff
        ScheduleStatus.PAUSED,     # reconciliation on server restart
    },
    ScheduleStatus.PAUSED: {
        ScheduleStatus.SCHEDULED,
        ScheduleStatus.CANCELLED,
    },
    ScheduleStatus.FAILED: {
        ScheduleStatus.SCHEDULED,  # retry
        ScheduleStatus.CANCELLED,
    },
    ScheduleStatus.MISSED: {
        ScheduleStatus.SCHEDULED,  # reschedule
        ScheduleStatus.CANCELLED,
    },
    ScheduleStatus.PUBLISHED: set(),  # terminal
    ScheduleStatus.CANCELLED: set(),  # terminal
}

@dataclass
class ScheduledPublish:
    id: str
    media_asset_id: str
    title: str
    scheduled_at_utc: datetime
    social_account_id: Optional[str] = None
    channel_id: Optional[str] = None
    platform_connection_id: Optional[str] = None
    channel_attribution: str = "unresolved"
    platform: SocialPlatform = SocialPlatform.YOUTUBE
    description: str = ""
    tags: List[str] = field(default_factory=list)
    category_id: str = "22"
    privacy_status: PrivacyStatus = PrivacyStatus.PRIVATE
    thumbnail_path: Optional[str] = None
    playlist_id: Optional[str] = None
    timezone: str = "UTC"
    status: ScheduleStatus = ScheduleStatus.SCHEDULED
    publish_record_id: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    def __post_init__(self):
        # Validate timezone awareness
        if self.scheduled_at_utc.tzinfo is None:
            raise InvalidScheduleTimeException("scheduled_at_utc must be timezone-aware (UTC).")
        # Ensure UTC normalization
        self.scheduled_at_utc = self.scheduled_at_utc.astimezone(timezone.utc)
        if not self.title or not self.title.strip():
            raise ScheduleDomainException("Schedule title cannot be empty.")

    def transition_to(
        self,
        new_status: ScheduleStatus,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if new_status not in VALID_TRANSITIONS.get(self.status, set()):
            raise InvalidScheduleStateTransitionException(self.status.value, new_status.value)

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1

        if error_code is not None:
            self.last_error_code = error_code
        if error_message is not None:
            self.last_error_message = error_message

    def mark_processing(self) -> None:
        self.transition_to(ScheduleStatus.PROCESSING)
        self.started_at = datetime.now(timezone.utc)
        self.attempt_count += 1

    def mark_published(self, publish_record_id: str) -> None:
        self.publish_record_id = publish_record_id
        self.completed_at = datetime.now(timezone.utc)
        self.last_error_code = None
        self.last_error_message = None
        self.transition_to(ScheduleStatus.PUBLISHED)

    def mark_failed(self, error_code: str, error_message: str) -> None:
        self.transition_to(ScheduleStatus.FAILED, error_code=error_code, error_message=error_message)

    def mark_missed(self, reason: str = "Planlanan yayın saati uygulama çevrimdışıyken aşıldı.") -> None:
        self.transition_to(
            ScheduleStatus.MISSED,
            error_code="MISSED_SCHEDULE",
            error_message=reason,
        )

    def mark_paused(
        self,
        error_code: str = "SERVER_RESTARTED",
        error_message: str = "Uygulama yeniden başlatıldığı için işlem duraklatıldı.",
    ) -> None:
        self.transition_to(ScheduleStatus.PAUSED, error_code=error_code, error_message=error_message)

    def reschedule(
        self,
        new_scheduled_at_utc: datetime,
        new_timezone: Optional[str] = None,
    ) -> None:
        if self.status not in (
            ScheduleStatus.SCHEDULED,
            ScheduleStatus.PAUSED,
            ScheduleStatus.FAILED,
            ScheduleStatus.MISSED,
        ):
            raise InvalidScheduleStateTransitionException(
                self.status.value,
                f"reschedule ({ScheduleStatus.SCHEDULED.value})",
            )

        if new_scheduled_at_utc.tzinfo is None:
            raise InvalidScheduleTimeException("new_scheduled_at_utc must be timezone-aware (UTC).")

        normalized_utc = new_scheduled_at_utc.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        if normalized_utc <= now:
            raise InvalidScheduleTimeException("Yeni planlama tarihi gelecekte olmalıdır.")

        self.scheduled_at_utc = normalized_utc
        if new_timezone:
            self.timezone = new_timezone

        # Reset errors and re-arm to SCHEDULED
        if self.status != ScheduleStatus.SCHEDULED:
            self.transition_to(ScheduleStatus.SCHEDULED)
        else:
            self.updated_at = now
            self.version += 1

        self.last_error_code = None
        self.last_error_message = None

    def cancel(self) -> None:
        self.transition_to(ScheduleStatus.CANCELLED)

    def update_details(
        self,
        title: str,
        description: str,
        tags: List[str],
        privacy_status: PrivacyStatus,
    ) -> None:
        if self.status not in (ScheduleStatus.SCHEDULED, ScheduleStatus.PAUSED):
            raise ScheduleDomainException(
                f"Cannot update schedule details in '{self.status.value}' status."
            )
        if not title or not title.strip():
            raise ScheduleDomainException("Schedule title cannot be empty.")

        self.title = title.strip()
        self.description = description.strip()
        self.tags = list(tags)
        self.privacy_status = privacy_status
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1

    def is_due(self, now_utc: datetime) -> bool:
        if self.status != ScheduleStatus.SCHEDULED:
            return False
        return now_utc.astimezone(timezone.utc) >= self.scheduled_at_utc

    def can_retry(self) -> bool:
        return self.status in (ScheduleStatus.FAILED, ScheduleStatus.MISSED) and self.attempt_count < self.max_attempts
