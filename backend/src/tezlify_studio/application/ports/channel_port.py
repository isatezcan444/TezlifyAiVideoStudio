from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from tezlify_studio.domain.value_objects.creator_models import (
    ChannelPlaylist,
    ChannelProfile,
    ChannelVideo,
    PlaylistItem,
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

    def list_playlist_items(
        self, playlist_id: str, max_results: int = 50
    ) -> List[PlaylistItem]:
        raise NotImplementedError("playlist items are not supported by this channel adapter")

    def create_playlist(
        self, title: str, description: str = "", privacy: str = "private"
    ) -> ChannelPlaylist:
        raise NotImplementedError("playlist creation is not supported by this channel adapter")

    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> PlaylistItem:
        raise NotImplementedError("playlist writes are not supported by this channel adapter")

    def remove_video_from_playlist(self, playlist_id: str, video_id: str) -> bool:
        raise NotImplementedError("playlist writes are not supported by this channel adapter")

    def set_video_thumbnail(
        self, video_id: str, image_bytes: bytes, content_type: str
    ) -> bool:
        raise NotImplementedError("thumbnail writes are not supported by this channel adapter")

    def update_playlist(
        self,
        playlist_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        privacy: Optional[str] = None,
    ) -> ChannelPlaylist:
        raise NotImplementedError("playlist updates are not supported by this channel adapter")

    def delete_playlist(self, playlist_id: str) -> bool:
        raise NotImplementedError("playlist deletes are not supported by this channel adapter")

    def move_playlist_item(
        self, playlist_id: str, video_id: str, position: int
    ) -> bool:
        raise NotImplementedError("playlist reordering is not supported by this channel adapter")

    def delete_video(self, video_id: str) -> bool:
        raise NotImplementedError("video deletes are not supported by this channel adapter")

    @abstractmethod
    def list_video_categories(self) -> List[Dict[str, str]]:
        pass
