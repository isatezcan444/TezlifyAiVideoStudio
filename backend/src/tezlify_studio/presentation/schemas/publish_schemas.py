from typing import Optional, List
from pydantic import BaseModel, Field

class SocialAccountResponse(BaseModel):
    id: str
    platform: str
    account_name: str
    channel_id: str
    channel_avatar_url: Optional[str] = None
    is_active: bool
    token_expires_at: Optional[str] = None
    is_expired: bool

class YouTubeAuthUrlResponse(BaseModel):
    auth_url: str
    state: str
    loopback_port: int = 0
    capabilities: List[str] = []
    requested_scopes: List[str] = []

class StartPublishRequest(BaseModel):
    media_asset_id: str
    channel_id: Optional[str] = Field(
        default=None,
        description="Target channel. Omit to use the currently selected channel.",
    )
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: List[str] = Field(default_factory=list)
    category_id: str = Field(default="22")
    privacy_status: str = Field(default="private", pattern="^(public|unlisted|private)$")
    thumbnail_path: Optional[str] = None
    playlist_id: Optional[str] = Field(
        default=None,
        description="Optional playlist to add the uploaded video to.",
    )

class PublishRecordResponse(BaseModel):
    id: str
    media_asset_id: str
    platform: str
    external_video_id: Optional[str] = None
    external_video_url: Optional[str] = None
    title: str
    description: str
    tags: List[str] = []
    category_id: str
    privacy_status: str
    status: str
    progress_percentage: int
    uploaded_bytes: int
    total_bytes: int
    thumbnail_path: Optional[str] = None
    playlist_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    published_at: Optional[str] = None
    channel_id: Optional[str] = None
    platform_connection_id: Optional[str] = None
    channel_attribution: str = "unresolved"

class PublishListResponse(BaseModel):
    items: List[PublishRecordResponse]
    total: int
