from typing import Any, Dict, List

from tezlify_studio.application.ports.channel_port import ChannelPort


class ListVideoCategoriesUseCase:
    def __init__(self, channel_port: ChannelPort):
        self.channel_port = channel_port

    def execute(self) -> Dict[str, List[Dict[str, str]]]:
        return {"items": self.channel_port.list_video_categories()}
