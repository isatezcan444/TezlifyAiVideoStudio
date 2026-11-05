from abc import ABC, abstractmethod
from typing import Optional

from tezlify_studio.domain.entities.channel_selection import ChannelSelection


class ChannelSelectionRepositoryPort(ABC):
    @abstractmethod
    def get(self) -> ChannelSelection:
        pass

    @abstractmethod
    def save(self, selection: ChannelSelection) -> ChannelSelection:
        pass
