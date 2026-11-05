from typing import List

from pydantic import BaseModel, Field


class ChannelResponse(BaseModel):
    id: str
    platform: str
    platform_connection_id: str
    channel_external_id: str
    channel_name: str
    channel_handle: str = ""
    avatar_url: str = ""
    description: str = ""
    is_primary: bool = False
    is_enabled: bool = True
    subscriber_count: int = 0
    uploads_playlist_id: str = ""
    connected_at: str = ""
    updated_at: str = ""


class ConnectionResponse(BaseModel):
    id: str
    platform: str
    account_external_id: str
    account_display_name: str
    connection_status: str
    granted_scopes: List[str] = []
    connected_at: str = ""
    last_refreshed_at: str = ""
    token_expires_at: str = ""
    token_expired: bool = False
    channels: List[ChannelResponse] = []
    channel_count: int = 0


class ConnectionListResponse(BaseModel):
    items: List[ConnectionResponse]
    total: int


class ChannelSelectionResponse(BaseModel):
    active_channel_id: str = ""
    default_platform: str = "youtube"
    updated_at: str = ""


class SelectChannelRequest(BaseModel):
    channel_id: str = Field(..., min_length=1)


class EnableChannelRequest(BaseModel):
    enabled: bool
