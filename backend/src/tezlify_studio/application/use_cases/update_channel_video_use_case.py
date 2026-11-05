from typing import Any, Dict

from tezlify_studio.application.ports.channel_port import ChannelPort


class UpdateChannelVideoUseCase:
    def __init__(self, channel_port: ChannelPort):
        self.channel_port = channel_port

    def execute(self, video_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"title", "description", "tags", "category_id", "privacy_status"}
        payload = {key: value for key, value in changes.items() if key in allowed and value is not None}
        if not payload:
            raise ValueError("Güncellenecek alan belirtilmedi.")
        if "title" in payload and not str(payload["title"]).strip():
            raise ValueError("Video başlığı boş olamaz.")
        if "privacy_status" in payload and payload["privacy_status"] not in (
            "public",
            "unlisted",
            "private",
        ):
            raise ValueError("Geçersiz gizlilik durumu.")
        video = self.channel_port.update_video(video_id, payload)
        return {"video": video, "source": "youtube_data_api", "updated": True}
