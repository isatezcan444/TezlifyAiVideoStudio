from typing import Any, Dict, List, Optional

from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort


class ListVideoCategoriesUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
    ):
        self.resolver = resolver
        self.gateway = gateway

    def execute(self, channel_id: Optional[str] = None) -> Dict[str, List[Dict[str, str]]]:
        context = self.resolver.resolve(channel_id)
        session = self.gateway.bind(context)
        return {"items": session.channel.list_video_categories()}
