from typing import Optional, List
from pydantic import BaseModel, Field

class CreateScheduledPublishRequest(BaseModel):
    media_asset_id: str = Field(..., min_length=1)
    channel_id: Optional[str] = Field(
        default=None,
        description="Target channel. Omit to use the currently selected channel.",
    )
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: List[str] = Field(default_factory=list)
    privacy_status: str = Field(default="private", pattern="^(public|unlisted|private)$")
    scheduled_at: str = Field(..., description="ISO 8601 formatted datetime with timezone offset (e.g. 2026-11-04T15:30:00+03:00)")
    timezone: str = Field(default="UTC")
    max_attempts: int = Field(default=3, ge=1, le=10)

class UpdateScheduledPublishRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = Field(None, pattern="^(public|unlisted|private)$")
    scheduled_at: Optional[str] = None
    timezone: Optional[str] = None

class RetryScheduledPublishRequest(BaseModel):
    scheduled_at: Optional[str] = None
    timezone: Optional[str] = None

class ScheduledPublishResponse(BaseModel):
    id: str
    media_asset_id: str
    social_account_id: Optional[str] = None
    platform: str
    title: str
    description: str
    tags: List[str] = []
    privacy_status: str
    scheduled_at_utc: str
    timezone: str
    status: str
    publish_record_id: Optional[str] = None
    attempt_count: int
    max_attempts: int
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str
    version: int
    channel_id: Optional[str] = None
    platform_connection_id: Optional[str] = None
    channel_attribution: str = "unresolved"

class ScheduledPublishListResponse(BaseModel):
    items: List[ScheduledPublishResponse]
    total: int

class SchedulerStatusResponse(BaseModel):
    is_running: bool
    check_interval_seconds: int
    last_tick_at: Optional[str] = None
    active_count: int
    upcoming_count: int
    failed_count: int
    missed_count: int
    published_count: int
