from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from tezlify_studio.application.use_cases.list_comments_use_case import ListCommentsUseCase
from tezlify_studio.application.use_cases.reply_to_comment_use_case import ReplyToCommentUseCase
from tezlify_studio.application.use_cases.set_comment_moderation_use_case import (
    SetCommentModerationUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_list_comments_use_case,
    get_reply_to_comment_use_case,
    get_set_comment_moderation_use_case,
)

router = APIRouter(prefix="/comments", tags=["Comments"])


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class ModerationRequest(BaseModel):
    status: str = Field(pattern="^(published|heldForReview|rejected)$")


@router.get("", response_model=Dict[str, Any])
def list_comments(
    video_id: Optional[str] = None,
    max_results: int = Query(25, ge=1, le=100),
    page_token: Optional[str] = None,
    use_case: ListCommentsUseCase = Depends(get_list_comments_use_case),
):
    return use_case.execute(video_id=video_id, max_results=max_results, page_token=page_token)


@router.post("/{comment_id}/reply", response_model=Dict[str, Any])
def reply_to_comment(
    comment_id: str,
    payload: ReplyRequest,
    use_case: ReplyToCommentUseCase = Depends(get_reply_to_comment_use_case),
):
    try:
        return use_case.execute(comment_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{comment_id}/moderation", response_model=Dict[str, Any])
def set_comment_moderation(
    comment_id: str,
    payload: ModerationRequest,
    use_case: SetCommentModerationUseCase = Depends(get_set_comment_moderation_use_case),
):
    return use_case.execute(comment_id, payload.status)
