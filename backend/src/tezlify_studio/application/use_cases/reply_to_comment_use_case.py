from typing import Any, Dict

from tezlify_studio.application.ports.comment_port import CommentPort


class ReplyToCommentUseCase:
    def __init__(self, comment_port: CommentPort):
        self.comment_port = comment_port

    def execute(self, parent_comment_id: str, text: str) -> Dict[str, Any]:
        clean = (text or "").strip()
        if not clean:
            raise ValueError("Yanıt metni boş olamaz.")
        if len(clean) > 10000:
            raise ValueError("Yanıt metni 10.000 karakteri aşamaz.")
        comment = self.comment_port.reply_to_comment(parent_comment_id, clean)
        return {"comment": comment, "source": "youtube_data_api"}
