from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    ScheduledPublishNotFoundException,
)
from tezlify_studio.application.dto.schedule_dto import ScheduledPublishDTO
from tezlify_studio.application.dto.mappers import scheduled_publish_to_dto

class CancelScheduledPublishUseCase:
    def __init__(self, schedule_repo: ScheduledPublishRepositoryPort):
        self.schedule_repo = schedule_repo

    def execute(self, schedule_id: str) -> ScheduledPublishDTO:
        schedule = self.schedule_repo.get_by_id(schedule_id)
        if not schedule:
            raise ScheduledPublishNotFoundException(schedule_id)

        schedule.cancel()
        saved = self.schedule_repo.save(schedule)
        return scheduled_publish_to_dto(saved)
