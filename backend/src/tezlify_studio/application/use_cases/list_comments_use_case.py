from typing import Any, Dict, Optional

from tezlify_studio.application.ports.comment_port import CommentPort


class ListCommentsUseCase:
    def __init__(self, comment_port: CommentPort):
        self.comment_port = comment_port

    def execute(
        self,
        video_id: Optional[str] = None,
        max_results: int = 25,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        comments = self.comment_port.list_comments(
            video_id=video_id, max_results=max_results, page_token=page_token
        )
        return {"items": comments, "source": "youtube_data_api"}
