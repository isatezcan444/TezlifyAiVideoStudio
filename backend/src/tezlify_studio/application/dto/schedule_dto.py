from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class ScheduledPublishDTO:
    id: str
    media_asset_id: str
    social_account_id: str
    platform: str
    title: str
    description: str
    tags: List[str]
    privacy_status: str
    scheduled_at_utc: str
    timezone: str
    status: str
    publish_record_id: Optional[str]
    attempt_count: int
    max_attempts: int
    last_error_code: Optional[str]
    last_error_message: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str
    updated_at: str
    version: int

@dataclass
class CreateScheduledPublishDTO:
    media_asset_id: str
    title: str
    scheduled_at_iso: str
    timezone: str = "UTC"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    privacy_status: str = "private"
    max_attempts: int = 3

@dataclass
class UpdateScheduledPublishDTO:
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = None
    scheduled_at_iso: Optional[str] = None
    timezone: Optional[str] = None

@dataclass
class SchedulerStatusDTO:
    is_running: bool
    check_interval_seconds: int
    last_tick_at: Optional[str]
    active_count: int
    upcoming_count: int
    failed_count: int
    missed_count: int
    published_count: int
