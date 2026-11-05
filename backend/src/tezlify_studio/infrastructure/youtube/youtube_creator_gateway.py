from typing import List, Optional

import httpx

from tezlify_studio.application.ports.channel_access_provider_port import (
    ChannelAccessProviderPort,
)
from tezlify_studio.application.ports.creator_gateway_port import (
    CreatorGatewayPort,
    CreatorSession,
)
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import PlatformDescriptor
from tezlify_studio.infrastructure.platform_catalog import PlatformCatalog
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YouTubeCreatorApi


class YouTubeCreatorGateway(CreatorGatewayPort):
    """Binds YouTube adapters to one validated channel context per request."""

    def __init__(
        self,
        access_provider: ChannelAccessProviderPort,
        client: Optional[httpx.Client] = None,
        catalog: Optional[PlatformCatalog] = None,
    ) -> None:
        self.access_provider = access_provider
        self._client = client
        self.catalog = catalog or PlatformCatalog()

    def list_platforms(self) -> List[PlatformDescriptor]:
        return self.catalog.list_platforms()

    def bind(self, context: ChannelContext) -> CreatorSession:
        access = self.access_provider.get_access(context)
        api = YouTubeCreatorApi(access, client=self._client)
        return CreatorSession(
            channel=api,
            analytics=api,
            comments=api,
            access=access,
        )
