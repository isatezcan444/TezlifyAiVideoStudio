from typing import List, Optional, Tuple
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.application.dto.schedule_dto import ScheduledPublishDTO
from tezlify_studio.application.dto.mappers import scheduled_publish_to_dto

class ListScheduledPublishesUseCase:
    def __init__(self, schedule_repo: ScheduledPublishRepositoryPort):
        self.schedule_repo = schedule_repo

    def execute(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[ScheduledPublishDTO], int]:
        sched_status = ScheduleStatus(status) if status else None
        items = self.schedule_repo.list_all(status=sched_status, limit=limit, offset=offset)
        total = self.schedule_repo.count(status=sched_status)
        return [scheduled_publish_to_dto(s) for s in items], total
