from abc import ABC, abstractmethod
from typing import List, Optional

from tezlify_studio.domain.entities.platform_connection import PlatformConnection


class PlatformConnectionRepositoryPort(ABC):
    @abstractmethod
    def save(self, connection: PlatformConnection) -> PlatformConnection:
        pass

    @abstractmethod
    def get_by_id(self, connection_id: str) -> Optional[PlatformConnection]:
        pass

    @abstractmethod
    def get_by_platform_account(
        self, platform: str, account_external_id: str
    ) -> Optional[PlatformConnection]:
        pass

    @abstractmethod
    def list_by_platform(
        self, platform: str, include_disconnected: bool = False
    ) -> List[PlatformConnection]:
        pass

    @abstractmethod
    def list_all(self, include_disconnected: bool = False) -> List[PlatformConnection]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def delete(self, connection_id: str) -> bool:
        pass
