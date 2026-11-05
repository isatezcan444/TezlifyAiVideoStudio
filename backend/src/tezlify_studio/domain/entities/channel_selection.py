from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ChannelSelection:
    """The channel the user is currently managing.

    This is a UI/session preference, not the channel identity itself.
    """

    id: str = "default"
    active_channel_id: Optional[str] = None
    default_platform: str = "youtube"
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def select(self, channel_id: str) -> None:
        self.active_channel_id = channel_id
        self.updated_at = datetime.now(timezone.utc)
