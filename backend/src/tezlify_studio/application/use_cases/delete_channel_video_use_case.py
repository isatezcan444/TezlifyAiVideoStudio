from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.domain.exceptions.creator_exceptions import CreatorApiException
from tezlify_studio.domain.value_objects.youtube_capabilities import CAPABILITY_COMMENTS


class DeleteChannelVideoUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
        capability_service: Optional[YouTubeCapabilityService] = None,
    ):
        self.resolver = resolver
        self.gateway = gateway
        self.capability_service = capability_service

    def execute(self, video_id: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        if not (video_id or "").strip():
            raise ValueError("Video belirtilmedi.")

        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(
                context.connection,
                CAPABILITY_COMMENTS,
                action="Videoyu YouTube'dan silme",
            )
        session = self.gateway.bind(context)
        deleted = session.channel.delete_video(video_id.strip())
        if not deleted:
            raise CreatorApiException("Video silinemedi.")
        return {
            "success": True,
            "video_id": video_id.strip(),
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
