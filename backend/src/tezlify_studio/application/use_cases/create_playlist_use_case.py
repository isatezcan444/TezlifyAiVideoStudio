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

_PRIVACY_VALUES = {"public", "unlisted", "private"}


class CreatePlaylistUseCase:
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
        title: str,
        description: str = "",
        privacy_status: str = "private",
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_title = (title or "").strip()
        if not clean_title:
            raise ValueError("Oynatma listesi adı boş olamaz.")
        if len(clean_title) > 150:
            raise ValueError("Oynatma listesi adı 150 karakteri aşamaz.")
        clean_description = (description or "").strip()
        if len(clean_description) > 5000:
            raise ValueError("Oynatma listesi açıklaması 5.000 karakteri aşamaz.")
        if privacy_status not in _PRIVACY_VALUES:
            raise ValueError("Geçersiz gizlilik durumu.")

        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(context.connection, CAPABILITY_COMMENTS)
        session = self.gateway.bind(context)
        playlist = session.channel.create_playlist(
            clean_title, clean_description, privacy_status
        )
        return {
            "playlist": playlist,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
