from typing import Any, Dict

from tezlify_studio.application.ports.comment_port import CommentPort


class SetCommentModerationUseCase:
    def __init__(self, comment_port: CommentPort):
        self.comment_port = comment_port

    def execute(self, comment_id: str, status: str) -> Dict[str, Any]:
        comment = self.comment_port.set_moderation_status(comment_id, status)
        return {"comment": comment, "source": "youtube_data_api"}
