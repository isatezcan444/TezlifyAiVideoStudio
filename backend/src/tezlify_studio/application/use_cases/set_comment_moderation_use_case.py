from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort


class SetCommentModerationUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
    ):
        self.resolver = resolver
        self.gateway = gateway

    def execute(
        self, comment_id: str, status: str, channel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self.resolver.resolve(channel_id)
        session = self.gateway.bind(context)
        comment = session.comments.set_moderation_status(comment_id, status)
        return {
            "comment": comment,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
