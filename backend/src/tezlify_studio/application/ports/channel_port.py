from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from tezlify_studio.domain.value_objects.creator_models import (
    ChannelPlaylist,
    ChannelProfile,
    ChannelVideo,
)


class ChannelPort(ABC):
    @abstractmethod
    def get_channel(self) -> ChannelProfile:
        pass

    @abstractmethod
    def list_videos(self, max_results: int = 25, page_token: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_video(self, video_id: str) -> ChannelVideo:
        pass

    @abstractmethod
    def update_video(self, video_id: str, changes: Dict[str, Any]) -> ChannelVideo:
        pass

    @abstractmethod
    def list_playlists(self, max_results: int = 25) -> List[ChannelPlaylist]:
        pass

    @abstractmethod
    def list_video_categories(self) -> List[Dict[str, str]]:
        pass
