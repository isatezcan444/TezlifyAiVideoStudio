from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from tezlify_studio.application.use_cases.get_channel_analytics_use_case import (
    GetChannelAnalyticsUseCase,
)
from tezlify_studio.application.use_cases.get_channel_overview_use_case import (
    GetChannelOverviewUseCase,
)
from tezlify_studio.application.use_cases.get_channel_video_use_case import (
    GetChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.list_channel_playlists_use_case import (
    ListChannelPlaylistsUseCase,
)
from tezlify_studio.application.use_cases.list_channel_videos_use_case import (
    ListChannelVideosUseCase,
)
from tezlify_studio.application.use_cases.list_video_categories_use_case import (
    ListVideoCategoriesUseCase,
)
from tezlify_studio.application.use_cases.update_channel_video_use_case import (
    UpdateChannelVideoUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_channel_analytics_use_case,
    get_channel_overview_use_case,
    get_channel_video_use_case,
    get_list_channel_playlists_use_case,
    get_list_channel_videos_use_case,
    get_list_video_categories_use_case,
    get_update_channel_video_use_case,
)

router = APIRouter(prefix="/channels", tags=["Channels"])


class UpdateVideoRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    category_id: Optional[str] = None
    privacy_status: Optional[str] = Field(default=None, pattern="^(public|unlisted|private)$")


@router.get("/youtube/overview", response_model=Dict[str, Any])
def get_youtube_overview(
    use_case: GetChannelOverviewUseCase = Depends(get_channel_overview_use_case),
):
    return use_case.execute()


@router.get("/youtube/videos", response_model=Dict[str, Any])
def list_youtube_videos(
    max_results: int = Query(25, ge=1, le=50),
    page_token: Optional[str] = None,
    use_case: ListChannelVideosUseCase = Depends(get_list_channel_videos_use_case),
):
    return use_case.execute(max_results=max_results, page_token=page_token)


@router.get("/youtube/videos/{video_id}", response_model=Dict[str, Any])
def get_youtube_video(
    video_id: str,
    use_case: GetChannelVideoUseCase = Depends(get_channel_video_use_case),
):
    return use_case.execute(video_id)


@router.patch("/youtube/videos/{video_id}", response_model=Dict[str, Any])
def update_youtube_video(
    video_id: str,
    payload: UpdateVideoRequest,
    use_case: UpdateChannelVideoUseCase = Depends(get_update_channel_video_use_case),
):
    # Metadata and privacy changes are explicit user actions and are only sent
    # to YouTube after this call; nothing runs automatically.
    try:
        return use_case.execute(video_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/youtube/playlists", response_model=Dict[str, Any])
def list_youtube_playlists(
    max_results: int = Query(25, ge=1, le=50),
    use_case: ListChannelPlaylistsUseCase = Depends(get_list_channel_playlists_use_case),
):
    return use_case.execute(max_results=max_results)


@router.get("/youtube/categories", response_model=Dict[str, Any])
def list_youtube_categories(
    use_case: ListVideoCategoriesUseCase = Depends(get_list_video_categories_use_case),
):
    return use_case.execute()


@router.get("/youtube/analytics", response_model=Dict[str, Any])
def get_youtube_analytics(
    range_key: str = Query("28", alias="range"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dimensions: Optional[str] = Query(None, description="Comma-separated dimensions, e.g. day,country"),
    include_revenue: bool = False,
    use_case: GetChannelAnalyticsUseCase = Depends(get_channel_analytics_use_case),
):
    dimension_list = [item.strip() for item in dimensions.split(",") if item.strip()] if dimensions else None
    try:
        return use_case.execute(
            range_key=range_key,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimension_list,
            include_revenue=include_revenue,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
