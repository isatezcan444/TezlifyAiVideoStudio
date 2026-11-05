from abc import ABC, abstractmethod
from typing import List, Optional

from tezlify_studio.domain.entities.channel_selection import ChannelSelection
from tezlify_studio.domain.value_objects.channel_context import ChannelContext


class ChannelContextResolverPort(ABC):
    @abstractmethod
    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        """Validates a channel id server-side and returns its full context.

        ``None`` falls back to the persisted selection, then to the first
        enabled channel.
        """
        pass

    @abstractmethod
    def list_contexts(
        self,
        platform: Optional[str] = None,
        include_disabled: bool = False,
        include_disconnected: bool = False,
    ) -> List[ChannelContext]:
        pass

    @abstractmethod
    def list_by_connection(self, connection_id: str) -> List[ChannelContext]:
        pass

    @abstractmethod
    def get_selection(self) -> ChannelSelection:
        pass

    @abstractmethod
    def select(self, channel_id: str) -> ChannelContext:
        pass

    @abstractmethod
    def clear_selection(self) -> None:
        pass
