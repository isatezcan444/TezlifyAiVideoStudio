from abc import ABC, abstractmethod

from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext


class ChannelAccessProviderPort(ABC):
    @abstractmethod
    def get_access(self, context: ChannelContext) -> ChannelAccess:
        """Returns a valid access token bound to the context's connection."""
        pass
