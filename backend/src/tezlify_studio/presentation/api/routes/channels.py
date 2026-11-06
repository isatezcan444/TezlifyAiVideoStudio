from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from tezlify_studio.application.dto.connection_dto import channel_to_dto
from tezlify_studio.application.services.channel_context_service import ChannelContextService
from tezlify_studio.application.use_cases.add_video_to_playlist_use_case import (
    AddVideoToPlaylistUseCase,
)
from tezlify_studio.application.use_cases.channel_selection_use_case import (
    ChannelSelectionUseCase,
)
from tezlify_studio.application.use_cases.create_playlist_use_case import (
    CreatePlaylistUseCase,
)
from tezlify_studio.application.use_cases.delete_channel_video_use_case import (
    DeleteChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.delete_playlist_use_case import (
    DeletePlaylistUseCase,
)
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
from tezlify_studio.application.use_cases.list_playlist_items_use_case import (
    ListPlaylistItemsUseCase,
)
from tezlify_studio.application.use_cases.list_video_categories_use_case import (
    ListVideoCategoriesUseCase,
)
from tezlify_studio.application.use_cases.move_playlist_item_use_case import (
    MovePlaylistItemUseCase,
)
from tezlify_studio.application.use_cases.remove_video_from_playlist_use_case import (
    RemoveVideoFromPlaylistUseCase,
)
from tezlify_studio.application.use_cases.set_video_thumbnail_use_case import (
    MAX_THUMBNAIL_BYTES,
    SetVideoThumbnailUseCase,
)
from tezlify_studio.application.use_cases.update_channel_video_use_case import (
    UpdateChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.update_playlist_use_case import (
    UpdatePlaylistUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_add_video_to_playlist_use_case,
    get_channel_analytics_use_case,
    get_channel_context_service,
    get_channel_overview_use_case,
    get_channel_selection_use_case,
    get_channel_video_use_case,
    get_create_playlist_use_case,
    get_delete_channel_video_use_case,
    get_delete_playlist_use_case,
    get_list_channel_playlists_use_case,
    get_list_channel_videos_use_case,
    get_list_playlist_items_use_case,
    get_list_video_categories_use_case,
    get_move_playlist_item_use_case,
    get_remove_video_from_playlist_use_case,
    get_set_video_thumbnail_use_case,
    get_update_channel_video_use_case,
    get_update_playlist_use_case,
)
from tezlify_studio.presentation.schemas.account_schemas import (
    ChannelSelectionResponse,
    EnableChannelRequest,
    SelectChannelRequest,
)

router = APIRouter(prefix="/channels", tags=["Channels"])

_CHANNEL_ID_DESCRIPTION = (
    "Target channel id. Omit to use the globally selected channel; the backend "
    "validates ownership and never trusts a channel id blindly."
)


class UpdateVideoRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    category_id: Optional[str] = None
    privacy_status: Optional[str] = Field(default=None, pattern="^(public|unlisted|private)$")


class CreatePlaylistRequest(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=5000)
    privacy_status: str = Field(default="private", pattern="^(public|unlisted|private)$")


class AddPlaylistItemRequest(BaseModel):
    video_id: str = Field(min_length=1, max_length=64)


class UpdatePlaylistRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = Field(default=None, max_length=5000)
    privacy_status: Optional[str] = Field(default=None, pattern="^(public|unlisted|private)$")


class MovePlaylistItemRequest(BaseModel):
    position: int = Field(ge=0)


@router.get("", response_model=Dict[str, Any])
def list_channels(
    platform: Optional[str] = Query(None),
    include_disabled: bool = Query(False),
    include_disconnected: bool = Query(False),
    resolver: ChannelContextService = Depends(get_channel_context_service),
    selection_use_case: ChannelSelectionUseCase = Depends(get_channel_selection_use_case),
):
    """Channels available for switching, already grouped by platform/account."""
    items = []
    for context in resolver.list_contexts(
        platform=platform,
        include_disabled=include_disabled,
        include_disconnected=include_disconnected,
    ):
        payload = channel_to_dto(context.channel).__dict__
        payload["account_display_name"] = context.connection.account_display_name
        payload["connection_status"] = context.connection.connection_status.value
        items.append(payload)

    selection = selection_use_case.get()
    return {
        "items": items,
        "total": len(items),
        "selection": selection.__dict__,
    }


@router.get("/selection", response_model=ChannelSelectionResponse)
def get_channel_selection(
    use_case: ChannelSelectionUseCase = Depends(get_channel_selection_use_case),
):
    return use_case.get().__dict__


@router.put("/selection", response_model=ChannelSelectionResponse)
def select_channel(
    payload: SelectChannelRequest,
    use_case: ChannelSelectionUseCase = Depends(get_channel_selection_use_case),
):
    return use_case.select(payload.channel_id).__dict__


@router.patch("/{channel_id}", response_model=Dict[str, Any])
def set_channel_enabled(
    channel_id: str,
    payload: EnableChannelRequest,
    use_case: ChannelSelectionUseCase = Depends(get_channel_selection_use_case),
):
    enabled = use_case.set_enabled(channel_id, payload.enabled)
    return {"channel_id": channel_id, "enabled": payload.enabled, "updated": enabled}


@router.get("/youtube/overview", response_model=Dict[str, Any])
def get_youtube_overview(
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: GetChannelOverviewUseCase = Depends(get_channel_overview_use_case),
):
    return use_case.execute(channel_id=channel_id)


@router.get("/youtube/videos", response_model=Dict[str, Any])
def list_youtube_videos(
    max_results: int = Query(25, ge=1, le=50),
    page_token: Optional[str] = None,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: ListChannelVideosUseCase = Depends(get_list_channel_videos_use_case),
):
    return use_case.execute(
        max_results=max_results, page_token=page_token, channel_id=channel_id
    )


@router.get("/youtube/videos/{video_id}", response_model=Dict[str, Any])
def get_youtube_video(
    video_id: str,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: GetChannelVideoUseCase = Depends(get_channel_video_use_case),
):
    return use_case.execute(video_id, channel_id=channel_id)


@router.patch("/youtube/videos/{video_id}", response_model=Dict[str, Any])
def update_youtube_video(
    video_id: str,
    payload: UpdateVideoRequest,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: UpdateChannelVideoUseCase = Depends(get_update_channel_video_use_case),
):
    # Metadata and privacy changes are explicit user actions and are only sent
    # to YouTube after this call; nothing runs automatically.
    try:
        return use_case.execute(
            video_id, payload.model_dump(exclude_none=True), channel_id=channel_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/youtube/playlists", response_model=Dict[str, Any])
def list_youtube_playlists(
    max_results: int = Query(25, ge=1, le=50),
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: ListChannelPlaylistsUseCase = Depends(get_list_channel_playlists_use_case),
):
    return use_case.execute(max_results=max_results, channel_id=channel_id)


@router.get("/youtube/playlists/{playlist_id}/items", response_model=Dict[str, Any])
def list_youtube_playlist_items(
    playlist_id: str,
    max_results: int = Query(50, ge=1, le=50),
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: ListPlaylistItemsUseCase = Depends(get_list_playlist_items_use_case),
):
    return use_case.execute(
        playlist_id, channel_id=channel_id, max_results=max_results
    )


@router.post("/youtube/playlists", response_model=Dict[str, Any], status_code=201)
def create_youtube_playlist(
    payload: CreatePlaylistRequest,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: CreatePlaylistUseCase = Depends(get_create_playlist_use_case),
):
    try:
        return use_case.execute(
            payload.title,
            payload.description,
            payload.privacy_status,
            channel_id=channel_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/youtube/playlists/{playlist_id}/items",
    response_model=Dict[str, Any],
    status_code=201,
)
def add_youtube_playlist_item(
    playlist_id: str,
    payload: AddPlaylistItemRequest,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: AddVideoToPlaylistUseCase = Depends(get_add_video_to_playlist_use_case),
):
    try:
        return use_case.execute(playlist_id, payload.video_id, channel_id=channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/youtube/playlists/{playlist_id}/items/{video_id}",
    response_model=Dict[str, Any],
)
def remove_youtube_playlist_item(
    playlist_id: str,
    video_id: str,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: RemoveVideoFromPlaylistUseCase = Depends(
        get_remove_video_from_playlist_use_case
    ),
):
    try:
        return use_case.execute(playlist_id, video_id, channel_id=channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/youtube/playlists/{playlist_id}", response_model=Dict[str, Any])
def update_youtube_playlist(
    playlist_id: str,
    payload: UpdatePlaylistRequest,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: UpdatePlaylistUseCase = Depends(get_update_playlist_use_case),
):
    try:
        return use_case.execute(
            playlist_id,
            payload.model_dump(exclude_none=True),
            channel_id=channel_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/youtube/playlists/{playlist_id}", response_model=Dict[str, Any])
def delete_youtube_playlist(
    playlist_id: str,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: DeletePlaylistUseCase = Depends(get_delete_playlist_use_case),
):
    return use_case.execute(playlist_id, channel_id=channel_id)


@router.patch(
    "/youtube/playlists/{playlist_id}/items/{video_id}",
    response_model=Dict[str, Any],
)
def move_youtube_playlist_item(
    playlist_id: str,
    video_id: str,
    payload: MovePlaylistItemRequest,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: MovePlaylistItemUseCase = Depends(get_move_playlist_item_use_case),
):
    try:
        return use_case.execute(
            playlist_id, video_id, payload.position, channel_id=channel_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/youtube/videos/{video_id}", response_model=Dict[str, Any])
def delete_youtube_video(
    video_id: str,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: DeleteChannelVideoUseCase = Depends(get_delete_channel_video_use_case),
):
    return use_case.execute(video_id, channel_id=channel_id)


@router.post(
    "/youtube/videos/{video_id}/thumbnail",
    response_model=Dict[str, Any],
)
async def set_youtube_video_thumbnail(
    video_id: str,
    file: UploadFile = File(...),
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: SetVideoThumbnailUseCase = Depends(get_set_video_thumbnail_use_case),
):
    content = await file.read(MAX_THUMBNAIL_BYTES + 1)
    try:
        return use_case.execute(
            video_id,
            content,
            file.content_type or "",
            channel_id=channel_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/youtube/categories", response_model=Dict[str, Any])
def list_youtube_categories(
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: ListVideoCategoriesUseCase = Depends(get_list_video_categories_use_case),
):
    return use_case.execute(channel_id=channel_id)


@router.get("/youtube/analytics", response_model=Dict[str, Any])
def get_youtube_analytics(
    range_key: str = Query("28", alias="range"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dimensions: Optional[str] = Query(None, description="Comma-separated dimensions, e.g. day,country"),
    include_revenue: bool = False,
    compare: bool = False,
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
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
            compare=compare,
            channel_id=channel_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
