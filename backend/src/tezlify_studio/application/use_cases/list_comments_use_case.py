from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort


class ListCommentsUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
    ):
        self.resolver = resolver
        self.gateway = gateway

    def execute(
        self,
        video_id: Optional[str] = None,
        max_results: int = 25,
        page_token: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = self.resolver.resolve(channel_id)
        session = self.gateway.bind(context)
        comments = session.comments.list_comments(
            video_id=video_id, max_results=max_results, page_token=page_token
        )
        return {
            "items": comments,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
