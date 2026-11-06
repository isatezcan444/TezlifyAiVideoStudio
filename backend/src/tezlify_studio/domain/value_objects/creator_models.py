from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


YOUTUBE_ANALYTICS_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "subscribersGained",
    "subscribersLost",
)


@dataclass(frozen=True)
class PlatformDescriptor:
    id: str
    display_name: str
    implemented: bool
    capabilities: Dict[str, bool]


@dataclass
class ChannelProfile:
    channel_id: str
    title: str
    description: str = ""
    avatar_url: Optional[str] = None
    custom_url: Optional[str] = None
    country: Optional[str] = None
    published_at: Optional[str] = None
    subscriber_count: Optional[int] = None
    video_count: Optional[int] = None
    view_count: Optional[int] = None
    hidden_subscriber_count: bool = False
    uploads_playlist_id: Optional[str] = None


@dataclass
class ChannelVideo:
    video_id: str
    title: str
    description: str = ""
    published_at: Optional[str] = None
    thumbnail_url: Optional[str] = None
    privacy_status: Optional[str] = None
    upload_status: Optional[str] = None
    duration_seconds: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    category_id: Optional[str] = None


@dataclass
class ChannelPlaylist:
    playlist_id: str
    title: str
    description: str = ""
    item_count: Optional[int] = None
    published_at: Optional[str] = None
    privacy_status: Optional[str] = None


@dataclass
class PlaylistItem:
    playlist_item_id: str
    playlist_id: str
    video_id: str
    title: str = ""
    thumbnail_url: Optional[str] = None
    position: Optional[int] = None
    published_at: Optional[str] = None


@dataclass
class AnalyticsRow:
    dimensions: Dict[str, str]
    metrics: Dict[str, float]


@dataclass
class AnalyticsResult:
    available: bool
    source: str = "analytics_api"
    reason: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    metrics: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    totals: Dict[str, float] = field(default_factory=dict)
    rows: List[AnalyticsRow] = field(default_factory=list)
    revenue: Optional[Dict[str, Any]] = None
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VideoComment:
    comment_id: str
    video_id: str
    author: str
    text: str
    like_count: int = 0
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    total_reply_count: int = 0
    moderation_status: Optional[str] = None


@dataclass
class DateRange:
    start_date: date
    end_date: date
    label: str

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1
