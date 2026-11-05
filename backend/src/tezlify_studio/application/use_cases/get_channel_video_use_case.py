from typing import Any, Dict

from tezlify_studio.application.ports.channel_port import ChannelPort


class GetChannelVideoUseCase:
    def __init__(self, channel_port: ChannelPort):
        self.channel_port = channel_port

    def execute(self, video_id: str) -> Dict[str, Any]:
        return {"video": self.channel_port.get_video(video_id), "source": "youtube_data_api"}
