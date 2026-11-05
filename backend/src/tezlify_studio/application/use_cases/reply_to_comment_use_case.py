from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort


class ReplyToCommentUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
    ):
        self.resolver = resolver
        self.gateway = gateway

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
        session = self.gateway.bind(context)
        comment = session.comments.reply_to_comment(parent_comment_id, clean)
        return {
            "comment": comment,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
