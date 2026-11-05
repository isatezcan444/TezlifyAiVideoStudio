from typing import Any, Dict, Optional

from tezlify_studio.application.ports.channel_port import ChannelPort


class ListChannelVideosUseCase:
    def __init__(self, channel_port: ChannelPort):
        self.channel_port = channel_port

    def execute(self, max_results: int = 25, page_token: Optional[str] = None) -> Dict[str, Any]:
        result = self.channel_port.list_videos(max_results=max_results, page_token=page_token)
        result["source"] = "youtube_data_api"
        return result
