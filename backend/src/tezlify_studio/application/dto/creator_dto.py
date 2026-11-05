from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tezlify_studio.domain.value_objects.creator_models import AnalyticsResult, ChannelProfile, ChannelVideo


@dataclass
class DashboardSnapshot:
    connected: bool
    range_days: int
    channel: Optional[ChannelProfile] = None
    analytics: Optional[AnalyticsResult] = None
    recent_videos: List[ChannelVideo] = field(default_factory=list)
    local_counts: Dict[str, Any] = field(default_factory=dict)
    upcoming_schedules: List[Dict[str, Any]] = field(default_factory=list)
    recent_publishes: List[Dict[str, Any]] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
