from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort


class GetChannelOverviewUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
    ):
        self.resolver = resolver
        self.gateway = gateway

    def execute(self, channel_id: Optional[str] = None) -> Dict[str, Any]:
        context = self.resolver.resolve(channel_id)
        session = self.gateway.bind(context)
        channel = session.channel.get_channel()
        playlists = session.channel.list_playlists(max_results=10)
        return {
            "channel": channel,
            "playlists": playlists,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
