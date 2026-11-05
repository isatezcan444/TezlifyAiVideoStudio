from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.domain.value_objects.youtube_capabilities import CAPABILITY_COMMENTS


class SetCommentModerationUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
        capability_service: Optional[YouTubeCapabilityService] = None,
    ):
        self.resolver = resolver
        self.gateway = gateway
        self.capability_service = capability_service

    def execute(
        self, comment_id: str, status: str, channel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(context.connection, CAPABILITY_COMMENTS)
        session = self.gateway.bind(context)
        comment = session.comments.set_moderation_status(comment_id, status)
        return {
            "comment": comment,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
