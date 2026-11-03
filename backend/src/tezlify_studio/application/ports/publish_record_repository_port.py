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
    def get_active_by_media(self, media_id: str, platform: SocialPlatform) -> Optional[PublishRecord]:
        pass

    @abstractmethod
    def list_by_platform(self, platform: SocialPlatform, limit: int = 50, offset: int = 0) -> List[PublishRecord]:
        pass

    @abstractmethod
    def list_all(self, limit: int = 50, offset: int = 0) -> List[PublishRecord]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        pass
