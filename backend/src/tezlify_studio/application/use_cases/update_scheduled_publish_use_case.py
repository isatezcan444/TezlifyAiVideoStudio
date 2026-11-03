import zoneinfo
from datetime import datetime, timezone
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.domain.enums.publish_status import PrivacyStatus
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    ScheduledPublishNotFoundException,
    InvalidScheduleTimeException,
)
from tezlify_studio.domain.services.schedule_timezone_validator import (
    validate_and_normalize_schedule_time,
)
from tezlify_studio.application.dto.schedule_dto import (
    UpdateScheduledPublishDTO,
    ScheduledPublishDTO,
)
from tezlify_studio.application.dto.mappers import scheduled_publish_to_dto

class UpdateScheduledPublishUseCase:
    def __init__(self, schedule_repo: ScheduledPublishRepositoryPort):
        self.schedule_repo = schedule_repo

    def execute(self, schedule_id: str, dto: UpdateScheduledPublishDTO) -> ScheduledPublishDTO:
        schedule = self.schedule_repo.get_by_id(schedule_id)
        if not schedule:
            raise ScheduledPublishNotFoundException(schedule_id)

        # 1. Update Details if provided
        new_title = dto.title if dto.title is not None else schedule.title
        new_desc = dto.description if dto.description is not None else schedule.description
        new_tags = dto.tags if dto.tags is not None else schedule.tags
        new_privacy = PrivacyStatus(dto.privacy_status) if dto.privacy_status else schedule.privacy_status

        schedule.update_details(
            title=new_title,
            description=new_desc,
            tags=new_tags,
            privacy_status=new_privacy,
        )

        # 2. Reschedule if new time or timezone provided
        if dto.scheduled_at_iso is not None:
            new_tz = dto.timezone or schedule.timezone
            sched_utc = validate_and_normalize_schedule_time(dto.scheduled_at_iso, new_tz)
            schedule.reschedule(new_scheduled_at_utc=sched_utc, new_timezone=new_tz)
        elif dto.timezone is not None:
            try:
                zoneinfo.ZoneInfo(dto.timezone)
            except Exception:
                raise InvalidScheduleTimeException(f"Geçersiz saat dilimi: '{dto.timezone}'")
            schedule.timezone = dto.timezone

        saved = self.schedule_repo.save(schedule)
        return scheduled_publish_to_dto(saved)
