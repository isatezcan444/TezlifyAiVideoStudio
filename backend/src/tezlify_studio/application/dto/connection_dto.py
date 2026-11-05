from dataclasses import dataclass, field
from typing import List

from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection


@dataclass
class ChannelDTO:
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


@dataclass
class ConnectionDTO:
    id: str
    platform: str
    account_external_id: str
    account_display_name: str
    connection_status: str
    granted_scopes: List[str] = field(default_factory=list)
    connected_at: str = ""
    last_refreshed_at: str = ""
    token_expires_at: str = ""
    token_expired: bool = False
    channels: List[ChannelDTO] = field(default_factory=list)

    @property
    def channel_count(self) -> int:
        return len(self.channels)


@dataclass
class ChannelSelectionDTO:
    active_channel_id: str
    default_platform: str
    updated_at: str


def iso_or_empty(value) -> str:
    return value.isoformat() if value else ""


def channel_to_dto(channel: PlatformChannel) -> ChannelDTO:
    return ChannelDTO(
        id=channel.id,
        platform=channel.platform.value,
        platform_connection_id=channel.platform_connection_id,
        channel_external_id=channel.channel_external_id,
        channel_name=channel.channel_name,
        channel_handle=channel.channel_handle or "",
        avatar_url=channel.avatar_url or "",
        description=channel.description or "",
        is_primary=channel.is_primary,
        is_enabled=channel.is_enabled,
        subscriber_count=channel.subscriber_count or 0,
        uploads_playlist_id=channel.uploads_playlist_id or "",
        connected_at=iso_or_empty(channel.created_at),
        updated_at=iso_or_empty(channel.updated_at),
    )


def channel_context_payload(context) -> dict:
    return {
        "channel_id": context.channel.id,
        "platform": context.channel.platform.value,
        "platform_connection_id": context.connection.id,
        "connection_status": context.connection.connection_status.value,
        "external_channel_id": context.channel.channel_external_id,
        "channel_name": context.channel.channel_name,
    }


def connection_to_dto(
    connection: PlatformConnection,
    channels: List[PlatformChannel],
) -> ConnectionDTO:
    return ConnectionDTO(
        id=connection.id,
        platform=connection.platform.value,
        account_external_id=connection.account_external_id,
        account_display_name=connection.account_display_name,
        connection_status=connection.connection_status.value,
        granted_scopes=list(connection.granted_scopes),
        connected_at=iso_or_empty(connection.connected_at),
        last_refreshed_at=iso_or_empty(connection.last_refreshed_at),
        token_expires_at=iso_or_empty(connection.token_expires_at),
        token_expired=connection.is_token_expired(),
        channels=[channel_to_dto(channel) for channel in channels],
    )
