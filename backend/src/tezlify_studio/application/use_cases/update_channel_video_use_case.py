from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import channel_context_payload
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort


class UpdateChannelVideoUseCase:
    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
    ):
        self.resolver = resolver
        self.gateway = gateway

    def execute(
        self,
        video_id: str,
        changes: Dict[str, Any],
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        allowed = {"title", "description", "tags", "category_id", "privacy_status"}
        payload = {key: value for key, value in changes.items() if key in allowed and value is not None}
        if not payload:
            raise ValueError("Güncellenecek alan belirtilmedi.")
        if "title" in payload and not str(payload["title"]).strip():
            raise ValueError("Video başlığı boş olamaz.")
        if "privacy_status" in payload and payload["privacy_status"] not in (
            "public",
            "unlisted",
            "private",
        ):
            raise ValueError("Geçersiz gizlilik durumu.")
        context = self.resolver.resolve(channel_id)
        session = self.gateway.bind(context)
        video = session.channel.update_video(video_id, payload)
        return {
            "video": video,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
            "updated": True,
        }
