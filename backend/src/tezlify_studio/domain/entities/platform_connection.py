from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from tezlify_studio.domain.enums.connection_status import ConnectionStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform


@dataclass
class PlatformConnection:
    """An authorized account on a platform.

    A connection owns its OAuth grant and is the only entity allowed to hold a
    token reference. Channels are separate identities owned by a connection.
    """

    id: str
    platform: SocialPlatform
    account_external_id: str
    account_display_name: str
    connection_status: ConnectionStatus = ConnectionStatus.ACTIVE
    token_reference: str = ""
    granted_scopes: List[str] = field(default_factory=list)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_refreshed_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.connection_status == ConnectionStatus.ACTIVE

    def is_token_expired(self, buffer_seconds: int = 120) -> bool:
        if not self.token_expires_at:
            return True
        expires = self.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return (expires.timestamp() - datetime.now(timezone.utc).timestamp()) < buffer_seconds

    def mark_refreshed(self, expires_at: datetime) -> None:
        self.token_expires_at = expires_at
        self.last_refreshed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        if self.connection_status in (ConnectionStatus.REAUTH_REQUIRED, ConnectionStatus.ERROR):
            self.connection_status = ConnectionStatus.ACTIVE

    def require_reauth(self) -> None:
        self.connection_status = ConnectionStatus.REAUTH_REQUIRED
        self.updated_at = datetime.now(timezone.utc)

    def disconnect(self) -> None:
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.updated_at = datetime.now(timezone.utc)
