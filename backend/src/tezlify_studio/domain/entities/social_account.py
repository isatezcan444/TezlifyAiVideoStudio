from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from tezlify_studio.domain.enums.publish_status import SocialPlatform

@dataclass
class SocialAccount:
    id: str
    platform: SocialPlatform
    account_name: str
    channel_id: str
    channel_avatar_url: Optional[str] = None
    is_active: bool = True
    token_expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_token_expired(self, buffer_seconds: int = 120) -> bool:
        if not self.token_expires_at:
            return True
        now = datetime.now(timezone.utc)
        # Handle naive datetime from db if needed
        expires = self.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return (expires.timestamp() - now.timestamp()) < buffer_seconds

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)
