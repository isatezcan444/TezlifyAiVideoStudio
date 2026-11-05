from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform

class ScheduledPublishRepositoryPort(ABC):
    @abstractmethod
    def save(self, record: ScheduledPublish) -> ScheduledPublish:
        """Persists or updates a ScheduledPublish entity."""
        pass

    @abstractmethod
    def get_by_id(self, schedule_id: str) -> Optional[ScheduledPublish]:
        """Fetches a ScheduledPublish by primary key."""
        pass

    @abstractmethod
    def get_due_records(self, now_utc: datetime, limit: int = 10) -> List[ScheduledPublish]:
        """Returns records in SCHEDULED status with scheduled_at_utc <= now_utc ordered by scheduled_at_utc ASC."""
        pass

    @abstractmethod
    def get_in_flight_processing_records(self) -> List[ScheduledPublish]:
        """Returns records currently in PROCESSING status (used for startup reconciliation)."""
        pass

    @abstractmethod
    def get_active_by_media(
        self,
        media_id: str,
        platform: SocialPlatform,
        channel_id: Optional[str] = None,
    ) -> Optional[ScheduledPublish]:
        """Checks if an active schedule exists for the media on this platform (SCHEDULED or PROCESSING)."""
        pass

    @abstractmethod
    def list_all(
        self,
        status: Optional[ScheduleStatus] = None,
        limit: int = 100,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> List[ScheduledPublish]:
        """Lists records with optional status filter, ordered by scheduled_at_utc ASC."""
        pass

    @abstractmethod
    def list_upcoming(
        self, now_utc: datetime, limit: int = 20, channel_id: Optional[str] = None
    ) -> List[ScheduledPublish]:
        """Returns future SCHEDULED records ordered by scheduled_at_utc ASC."""
        pass

    @abstractmethod
    def fail_pending_for_connection(
        self, connection_id: str, error_code: str, error_message: str
    ) -> int:
        """Fails only the pending schedules owned by a disconnected connection."""
        pass

    @abstractmethod
    def claim_for_processing(self, schedule_id: str, expected_version: int) -> bool:
        """
        Atomically transitions record from SCHEDULED to PROCESSING, incrementing attempt_count and version.
        Returns True if claimed successfully, False if already claimed or version mismatched.
        """
        pass

    @abstractmethod
    def count(
        self,
        status: Optional[ScheduleStatus] = None,
        channel_id: Optional[str] = None,
    ) -> int:
        """Returns total count of records matching optional status and channel."""
        pass

    @abstractmethod
    def delete(self, schedule_id: str) -> bool:
        """Deletes a schedule record."""
        pass
