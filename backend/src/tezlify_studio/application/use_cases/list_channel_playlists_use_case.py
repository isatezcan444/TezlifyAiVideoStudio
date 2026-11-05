from typing import Any, Dict

from tezlify_studio.application.ports.channel_port import ChannelPort


class ListChannelPlaylistsUseCase:
    def __init__(self, channel_port: ChannelPort):
        self.channel_port = channel_port

    def execute(self, max_results: int = 25) -> Dict[str, Any]:
        return {
            "items": self.channel_port.list_playlists(max_results=max_results),
            "source": "youtube_data_api",
        }
