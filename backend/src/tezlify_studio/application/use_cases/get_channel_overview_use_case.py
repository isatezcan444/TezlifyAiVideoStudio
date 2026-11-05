from typing import Any, Dict

from tezlify_studio.application.ports.channel_port import ChannelPort


class GetChannelOverviewUseCase:
    def __init__(self, channel_port: ChannelPort):
        self.channel_port = channel_port

    def execute(self) -> Dict[str, Any]:
        channel = self.channel_port.get_channel()
        playlists = self.channel_port.list_playlists(max_results=10)
        return {
            "channel": channel,
            "playlists": playlists,
            "source": "youtube_data_api",
        }
