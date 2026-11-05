import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import Optional
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    ScheduledPublishNotFoundException,
    InvalidScheduleStateTransitionException,
    InvalidScheduleTimeException,
)
from tezlify_studio.application.dto.schedule_dto import ScheduledPublishDTO
from tezlify_studio.domain.exceptions.creator_exceptions import CreatorStudioException
from tezlify_studio.application.dto.mappers import scheduled_publish_to_dto

class RetryFailedScheduledPublishUseCase:
    def __init__(self, schedule_repo: ScheduledPublishRepositoryPort):
        self.schedule_repo = schedule_repo

    def execute(
        self,
        schedule_id: str,
        new_scheduled_at_iso: Optional[str] = None,
        new_timezone: Optional[str] = None,
    ) -> ScheduledPublishDTO:
        schedule = self.schedule_repo.get_by_id(schedule_id)
        if not schedule:
            raise ScheduledPublishNotFoundException(schedule_id)

        if schedule.status not in (ScheduleStatus.FAILED, ScheduleStatus.MISSED, ScheduleStatus.PAUSED):
            raise InvalidScheduleStateTransitionException(
                schedule.status.value,
                ScheduleStatus.SCHEDULED.value,
            )

        if not schedule.channel_id:
            raise CreatorStudioException(
                "Bu planın kanalı belirsiz (unresolved). Yanlış kanala yayınlamamak için "
                "tekrar deneme yapılmadı; videoyu hedef kanalı seçerek yeniden planlayın.",
                "CHANNEL_UNRESOLVED",
            )

        now_utc = datetime.now(timezone.utc)

        if new_scheduled_at_iso:
            try:
                raw_dt = datetime.fromisoformat(new_scheduled_at_iso)
            except Exception as e:
                raise InvalidScheduleTimeException(f"Geçersiz ISO 8601 tarih: {str(e)}")
            if raw_dt.tzinfo is None:
                raise InvalidScheduleTimeException("Tarih zaman dilimi (timezone) bilgisi içermelidir.")
            target_utc = raw_dt.astimezone(timezone.utc)
            tz_str = new_timezone or schedule.timezone
            if new_timezone:
                try:
                    zoneinfo.ZoneInfo(tz_str)
                except Exception:
                    raise InvalidScheduleTimeException(f"Geçersiz saat dilimi: {tz_str}")
        else:
            # If no time provided, re-arm for immediate processing in next scheduler tick (+10 seconds)
            target_utc = now_utc + timedelta(seconds=10)
            tz_str = schedule.timezone

        # Reset attempts if user is manually triggering retry
        if schedule.attempt_count >= schedule.max_attempts:
            schedule.attempt_count = max(0, schedule.max_attempts - 1)

        schedule.scheduled_at_utc = target_utc
        schedule.timezone = tz_str
        schedule.last_error_code = None
        schedule.last_error_message = None
        schedule.transition_to(ScheduleStatus.SCHEDULED)

        saved = self.schedule_repo.save(schedule)
        return scheduled_publish_to_dto(saved)
