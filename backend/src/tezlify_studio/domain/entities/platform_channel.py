from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from tezlify_studio.domain.enums.publish_status import SocialPlatform


@dataclass
class PlatformChannel:
    """A channel/profile identity managed through a platform connection."""

    id: str
    platform_connection_id: str
    platform: SocialPlatform
    channel_external_id: str
    channel_name: str
    channel_handle: Optional[str] = None
    avatar_url: Optional[str] = None
    description: str = ""
    is_primary: bool = False
    is_enabled: bool = True
    subscriber_count: Optional[int] = None
    uploads_playlist_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def apply_profile(
        self,
        *,
        name: str,
        handle: Optional[str],
        avatar_url: Optional[str],
        description: str,
        subscriber_count: Optional[int],
        uploads_playlist_id: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.channel_name = name or self.channel_name
        self.channel_handle = handle
        self.avatar_url = avatar_url
        self.description = description or ""
        self.subscriber_count = subscriber_count
        self.uploads_playlist_id = uploads_playlist_id
        if metadata is not None:
            self.metadata = metadata
        self.updated_at = datetime.now(timezone.utc)
