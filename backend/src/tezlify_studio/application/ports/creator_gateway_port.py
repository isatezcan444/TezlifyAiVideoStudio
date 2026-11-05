from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from tezlify_studio.application.ports.analytics_port import AnalyticsPort
from tezlify_studio.application.ports.channel_port import ChannelPort
from tezlify_studio.application.ports.comment_port import CommentPort
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import PlatformDescriptor


@dataclass(frozen=True)
class CreatorSession:
    """Platform ports bound to one validated channel + connection pair."""

    channel: ChannelPort
    analytics: AnalyticsPort
    comments: CommentPort
    access: ChannelAccess


class CreatorGatewayPort(ABC):
    @abstractmethod
    def list_platforms(self) -> List[PlatformDescriptor]:
        pass

    @abstractmethod
    def bind(self, context: ChannelContext) -> CreatorSession:
        """Builds adapters that can only talk to ``context``'s channel."""
        pass
