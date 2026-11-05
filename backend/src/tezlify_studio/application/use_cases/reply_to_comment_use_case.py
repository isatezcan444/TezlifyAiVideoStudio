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


class ReplyToCommentUseCase:
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
        self,
        parent_comment_id: str,
        text: str,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean = (text or "").strip()
        if not clean:
            raise ValueError("Yanıt metni boş olamaz.")
        if len(clean) > 10000:
            raise ValueError("Yanıt metni 10.000 karakteri aşamaz.")
        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(context.connection, CAPABILITY_COMMENTS)
        session = self.gateway.bind(context)
        comment = session.comments.reply_to_comment(parent_comment_id, clean)
        return {
            "comment": comment,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
