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


class UpdatePlaylistUseCase:
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
        playlist_id: str,
        changes: Dict[str, Any],
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not (playlist_id or "").strip():
            raise ValueError("Oynatma listesi belirtilmedi.")

        title = changes.get("title")
        description = changes.get("description")
        privacy_status = changes.get("privacy_status")

        if title is not None:
            title = title.strip()
            if not title:
                raise ValueError("Oynatma listesi adı boş olamaz.")
            if len(title) > 150:
                raise ValueError("Oynatma listesi adı 150 karakteri aşamaz.")
        if description is not None:
            description = description.strip()
            if len(description) > 5000:
                raise ValueError("Oynatma listesi açıklaması 5.000 karakteri aşamaz.")
        if privacy_status is not None and privacy_status not in _PRIVACY_VALUES:
            raise ValueError("Geçersiz gizlilik durumu.")
        if title is None and description is None and privacy_status is None:
            raise ValueError("Güncellenecek alan belirtilmedi.")

        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(
                context.connection,
                CAPABILITY_COMMENTS,
                action="Oynatma listesini güncelleme",
            )
        session = self.gateway.bind(context)
        playlist = session.channel.update_playlist(
            playlist_id.strip(),
            title=title,
            description=description,
            privacy=privacy_status,
        )
        return {
            "playlist": playlist,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
