from abc import ABC, abstractmethod
from typing import List, Optional

from tezlify_studio.domain.value_objects.creator_models import VideoComment


class CommentPort(ABC):
    @abstractmethod
    def list_comments(
        self,
        video_id: Optional[str] = None,
        max_results: int = 25,
        page_token: Optional[str] = None,
    ) -> List[VideoComment]:
        pass

    @abstractmethod
    def reply_to_comment(self, parent_comment_id: str, text: str) -> VideoComment:
        pass

    @abstractmethod
    def set_moderation_status(self, comment_id: str, status: str) -> VideoComment:
        pass
