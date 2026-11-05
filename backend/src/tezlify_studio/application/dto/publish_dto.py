from dataclasses import dataclass
from typing import Optional, List

@dataclass
class SocialAccountDTO:
    id: str
    platform: str
    account_name: str
    channel_id: str
    channel_avatar_url: Optional[str]
    is_active: bool
    is_token_valid: bool
    created_at: str

@dataclass
class PublishRecordDTO:
    id: str
    media_asset_id: str
    platform: str
    external_video_id: Optional[str]
    external_video_url: Optional[str]
    title: str
    description: str
    tags: List[str]
    category_id: str
    privacy_status: str
    status: str
    progress_percentage: int
    uploaded_bytes: int
    total_bytes: int
    thumbnail_path: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    published_at: Optional[str]
    channel_id: Optional[str] = None
    platform_connection_id: Optional[str] = None
    channel_attribution: str = "unresolved"

@dataclass
class StartPublishRequestDTO:
    media_asset_id: str
    title: str
    description: str = ""
    tags: List[str] = None
    category_id: str = "22"
    privacy_status: str = "private"
    thumbnail_path: Optional[str] = None
    channel_id: Optional[str] = None

@dataclass
class YouTubeAuthUrlResponseDTO:
    auth_url: str
    state: str
    loopback_port: int

@dataclass
class PublishListResponseDTO:
    items: List[PublishRecordDTO]
    total: int
