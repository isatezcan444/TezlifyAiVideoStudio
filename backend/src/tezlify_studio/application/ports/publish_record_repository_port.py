from abc import ABC, abstractmethod
from typing import List, Optional
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import SocialPlatform

class PublishRecordRepositoryPort(ABC):
    @abstractmethod
    def save(self, record: PublishRecord) -> PublishRecord:
        pass

    @abstractmethod
    def get_by_id(self, record_id: str) -> Optional[PublishRecord]:
        pass

    @abstractmethod
    def get_active_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[PublishRecord]:
        pass

    @abstractmethod
    def get_latest_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[PublishRecord]:
        pass

    @abstractmethod
    def list_by_platform(
        self,
        platform: SocialPlatform,
        limit: int = 50,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> List[PublishRecord]:
        pass

    @abstractmethod
    def count_by_channel(self, channel_id: str) -> int:
        pass

    @abstractmethod
    def fail_pending_for_connection(
        self, connection_id: str, error_code: str, error_message: str
    ) -> int:
        pass

    @abstractmethod
    def list_all(
        self, limit: int = 50, offset: int = 0, channel_id: Optional[str] = None
    ) -> List[PublishRecord]:
        pass

    @abstractmethod
    def get_in_flight_records(self) -> List[PublishRecord]:
        """Returns records currently in non-terminal/in-flight states (PENDING, AUTHENTICATING, UPLOADING)."""
        pass

    @abstractmethod
    def count(self, channel_id: Optional[str] = None) -> int:
        pass

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        pass
