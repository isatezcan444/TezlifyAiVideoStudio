from abc import ABC, abstractmethod
from typing import Optional

class TokenStoragePort(ABC):
    @abstractmethod
    def store_tokens(
        self,
        account_id: str,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> None:
        """Stores tokens in secure storage (e.g., macOS Keychain)."""
        pass

    @abstractmethod
    def get_access_token(self, account_id: str) -> Optional[str]:
        pass

    @abstractmethod
    def get_refresh_token(self, account_id: str) -> Optional[str]:
        pass

    @abstractmethod
    def delete_tokens(self, account_id: str) -> None:
        """Purges tokens from secure storage."""
        pass
