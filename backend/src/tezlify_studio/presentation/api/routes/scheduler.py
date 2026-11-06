from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from tezlify_studio.presentation.schemas.schedule_schemas import (
    CreateScheduledPublishRequest,
    UpdateScheduledPublishRequest,
    RetryScheduledPublishRequest,
    ScheduledPublishResponse,
    ScheduledPublishListResponse,
    SchedulerStatusResponse,
)
from tezlify_studio.application.dto.schedule_dto import (
    CreateScheduledPublishDTO,
    UpdateScheduledPublishDTO,
)
from tezlify_studio.application.use_cases.create_scheduled_publish_use_case import (
    CreateScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.update_scheduled_publish_use_case import (
    UpdateScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.cancel_scheduled_publish_use_case import (
    CancelScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.get_scheduled_publish_use_case import (
    GetScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.list_scheduled_publishes_use_case import (
    ListScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.get_upcoming_publishes_use_case import (
    GetUpcomingPublishesUseCase,
)
from tezlify_studio.application.use_cases.retry_failed_scheduled_publish_use_case import (
    RetryFailedScheduledPublishUseCase,
)
from tezlify_studio.infrastructure.scheduler.scheduler_service import PublishSchedulerService
from tezlify_studio.presentation.dependencies.container import (
    get_create_scheduled_publish_use_case,
    get_update_scheduled_publish_use_case,
    get_cancel_scheduled_publish_use_case,
    get_get_scheduled_publish_use_case,
    get_list_scheduled_publishes_use_case,
    get_upcoming_publishes_use_case,
    get_retry_scheduled_publish_use_case,
    get_scheduler_service,
)

router = APIRouter(prefix="/scheduler", tags=["Publishing Scheduler"])

_CHANNEL_ID_DESCRIPTION = (
    "Target channel id. Omit to use the globally selected channel; the backend "
    "validates ownership and never trusts a channel id blindly."
)


@router.post("", response_model=ScheduledPublishResponse, status_code=status.HTTP_201_CREATED)
def create_scheduled_publish(
    req: CreateScheduledPublishRequest,
    use_case: CreateScheduledPublishUseCase = Depends(get_create_scheduled_publish_use_case),
):
    dto = CreateScheduledPublishDTO(
        media_asset_id=req.media_asset_id,
        title=req.title,
        description=req.description,
        tags=req.tags,
        category_id=req.category_id,
        privacy_status=req.privacy_status,
        thumbnail_path=req.thumbnail_path,
        playlist_id=req.playlist_id,
        scheduled_at_iso=req.scheduled_at,
        timezone=req.timezone,
        max_attempts=req.max_attempts,
        channel_id=req.channel_id,
    )
    result = use_case.execute(dto)
    return ScheduledPublishResponse(**result.__dict__)


@router.get("", response_model=ScheduledPublishListResponse)
def list_scheduled_publishes(
    status: Optional[str] = Query(None, description="Filter by status (scheduled, processing, published, failed, paused, cancelled, missed)"),
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    use_case: ListScheduledPublishesUseCase = Depends(get_list_scheduled_publishes_use_case),
):
    items, total = use_case.execute(
        status=status, limit=limit, offset=offset, channel_id=channel_id
    )
    return ScheduledPublishListResponse(
        items=[ScheduledPublishResponse(**i.__dict__) for i in items],
        total=total,
    )


@router.get("/upcoming", response_model=List[ScheduledPublishResponse])
def get_upcoming_publishes(
    limit: int = Query(20, ge=1, le=100),
    channel_id: Optional[str] = Query(None, description=_CHANNEL_ID_DESCRIPTION),
    use_case: GetUpcomingPublishesUseCase = Depends(get_upcoming_publishes_use_case),
):
    items = use_case.execute(limit=limit, channel_id=channel_id)
    return [ScheduledPublishResponse(**i.__dict__) for i in items]


@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status(
    scheduler_service: PublishSchedulerService = Depends(get_scheduler_service),
):
    status_dto = scheduler_service.get_status()
    return SchedulerStatusResponse(**status_dto.__dict__)


@router.get("/{id}", response_model=ScheduledPublishResponse)
def get_scheduled_publish(
    id: str = Path(..., description="Schedule UUID"),
    use_case: GetScheduledPublishUseCase = Depends(get_get_scheduled_publish_use_case),
):
    result = use_case.execute(schedule_id=id)
    return ScheduledPublishResponse(**result.__dict__)


@router.patch("/{id}", response_model=ScheduledPublishResponse)
def update_scheduled_publish(
    id: str = Path(..., description="Schedule UUID"),
    req: UpdateScheduledPublishRequest = ...,
    use_case: UpdateScheduledPublishUseCase = Depends(get_update_scheduled_publish_use_case),
):
    dto = UpdateScheduledPublishDTO(
        title=req.title,
        description=req.description,
        tags=req.tags,
        privacy_status=req.privacy_status,
        scheduled_at_iso=req.scheduled_at,
        timezone=req.timezone,
    )
    result = use_case.execute(schedule_id=id, dto=dto)
    return ScheduledPublishResponse(**result.__dict__)


@router.delete("/{id}")
def cancel_scheduled_publish(
    id: str = Path(..., description="Schedule UUID"),
    use_case: CancelScheduledPublishUseCase = Depends(get_cancel_scheduled_publish_use_case),
):
    result = use_case.execute(schedule_id=id)
    return {"success": True, "message": "Yayın planı iptal edildi.", "item": ScheduledPublishResponse(**result.__dict__)}


@router.post("/{id}/retry", response_model=ScheduledPublishResponse)
def retry_failed_scheduled_publish(
    id: str = Path(..., description="Schedule UUID"),
    req: Optional[RetryScheduledPublishRequest] = None,
    use_case: RetryFailedScheduledPublishUseCase = Depends(get_retry_scheduled_publish_use_case),
):
    result = use_case.execute(
        schedule_id=id,
        new_scheduled_at_iso=req.scheduled_at if req else None,
        new_timezone=req.timezone if req else None,
    )
    return ScheduledPublishResponse(**result.__dict__)
