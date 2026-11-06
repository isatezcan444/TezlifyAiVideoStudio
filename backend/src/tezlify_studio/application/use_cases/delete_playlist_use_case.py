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


class DeletePlaylistUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
        capability_service: Optional[YouTubeCapabilityService] = None,
    ):
        self.resolver = resolver
        self.gateway = gateway
        self.capability_service = capability_service

    def execute(self, playlist_id: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        if not (playlist_id or "").strip():
            raise ValueError("Oynatma listesi belirtilmedi.")

        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(
                context.connection,
                CAPABILITY_COMMENTS,
                action="Oynatma listesini silme",
            )
        session = self.gateway.bind(context)
        deleted = session.channel.delete_playlist(playlist_id.strip())
        if not deleted:
            raise CreatorApiException("Oynatma listesi silinemedi.")
        return {
            "success": True,
            "playlist_id": playlist_id.strip(),
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
