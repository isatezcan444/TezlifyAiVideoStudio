from abc import ABC, abstractmethod
from typing import Optional
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.enums.publish_status import SocialPlatform

class SocialAccountRepositoryPort(ABC):
    @abstractmethod
    def save(self, account: SocialAccount) -> SocialAccount:
        pass

    @abstractmethod
    def get_by_id(self, account_id: str) -> Optional[SocialAccount]:
        pass

    @abstractmethod
    def get_active_by_platform(self, platform: SocialPlatform) -> Optional[SocialAccount]:
        pass

    @abstractmethod
    def delete(self, account_id: str) -> bool:
        pass
