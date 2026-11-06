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
from tezlify_studio.domain.value_objects.youtube_capabilities import CAPABILITY_UPLOAD

_THUMBNAIL_SIGNATURES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024


class SetVideoThumbnailUseCase:
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
        video_id: str,
        image_bytes: bytes,
        content_type: str,
        channel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not (video_id or "").strip():
            raise ValueError("Video belirtilmedi.")
        signature = _THUMBNAIL_SIGNATURES.get((content_type or "").lower())
        if not signature:
            raise ValueError("Kapak görseli JPEG veya PNG olmalıdır.")
        if not image_bytes:
            raise ValueError("Kapak görseli boş olamaz.")
        if len(image_bytes) > MAX_THUMBNAIL_BYTES:
            raise ValueError("Kapak görseli en fazla 2 MB olabilir.")
        if not image_bytes.startswith(signature):
            raise ValueError("Dosya içeriği belirtilen görsel biçimiyle uyuşmuyor.")

        context = self.resolver.resolve(channel_id)
        if self.capability_service:
            self.capability_service.require(context.connection, CAPABILITY_UPLOAD)
        session = self.gateway.bind(context)
        updated = session.channel.set_video_thumbnail(
            video_id.strip(), image_bytes, content_type.lower()
        )
        if not updated:
            raise CreatorApiException("Video kapağı güncellenemedi.")
        return {
            "video_id": video_id.strip(),
            "updated": True,
            "context": channel_context_payload(context),
            "source": "youtube_data_api",
        }
