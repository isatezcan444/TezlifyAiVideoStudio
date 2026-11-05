from dataclasses import dataclass

from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection


@dataclass(frozen=True)
class ChannelContext:
    """Resolved, server-validated channel + connection pair.

    Every platform operation must carry a ChannelContext. Tokens are resolved
    from ``connection.id`` only, never from the channel id alone.
    """

    channel: PlatformChannel
    connection: PlatformConnection

    @property
    def channel_id(self) -> str:
        return self.channel.id

    @property
    def connection_id(self) -> str:
        return self.connection.id

    @property
    def external_channel_id(self) -> str:
        return self.channel.channel_external_id
