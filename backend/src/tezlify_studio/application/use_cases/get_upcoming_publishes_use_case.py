from datetime import datetime, timezone
from typing import List, Optional
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.dto.schedule_dto import ScheduledPublishDTO
from tezlify_studio.application.dto.mappers import scheduled_publish_to_dto

class GetUpcomingPublishesUseCase:
    def __init__(self, schedule_repo: ScheduledPublishRepositoryPort):
        self.schedule_repo = schedule_repo

    def execute(
        self, limit: int = 20, channel_id: Optional[str] = None
    ) -> List[ScheduledPublishDTO]:
        now_utc = datetime.now(timezone.utc)
        items = self.schedule_repo.list_upcoming(
            now_utc=now_utc, limit=limit, channel_id=channel_id
        )
        return [scheduled_publish_to_dto(s) for s in items]
