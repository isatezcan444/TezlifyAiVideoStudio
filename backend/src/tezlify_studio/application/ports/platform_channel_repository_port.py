from abc import ABC, abstractmethod
from typing import List, Optional

from tezlify_studio.domain.entities.platform_channel import PlatformChannel


class PlatformChannelRepositoryPort(ABC):
    @abstractmethod
    def save(self, channel: PlatformChannel) -> PlatformChannel:
        pass

    @abstractmethod
    def get_by_id(self, channel_id: str) -> Optional[PlatformChannel]:
        pass

    @abstractmethod
    def get_by_connection_external(
        self, connection_id: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        pass

    @abstractmethod
    def find_by_external_id(
        self, platform: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        pass

    @abstractmethod
    def list_by_connection(self, connection_id: str) -> List[PlatformChannel]:
        pass

    @abstractmethod
    def list_enabled(self, platform: Optional[str] = None) -> List[PlatformChannel]:
        pass

    @abstractmethod
    def set_enabled(self, channel_id: str, enabled: bool) -> Optional[PlatformChannel]:
        pass

    @abstractmethod
    def count(self, enabled_only: bool = True) -> int:
        pass

    @abstractmethod
    def delete(self, channel_id: str) -> bool:
        pass
