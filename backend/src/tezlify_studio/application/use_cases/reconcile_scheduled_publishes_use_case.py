from datetime import datetime, timezone, timedelta
from typing import List, Tuple
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import PublishStatus

class ReconcileScheduledPublishesUseCase:
    """
    On application startup and scheduler initialization:
    1. Reconciles in-flight 'PROCESSING' tasks from crashed or killed server runs.
    2. Identifies 'SCHEDULED' tasks whose due time passed while the server was offline
       beyond the configured grace window, transitioning them to 'MISSED'.
    """
    def __init__(
        self,
        schedule_repo: ScheduledPublishRepositoryPort,
        publish_repo: PublishRecordRepositoryPort,
        grace_period_minutes: int = 60,
    ):
        self.schedule_repo = schedule_repo
        self.publish_repo = publish_repo
        self.grace_period_minutes = grace_period_minutes

    def execute(self) -> Tuple[int, int]:
        now_utc = datetime.now(timezone.utc)
        reconciled_in_flight_count = 0
        marked_missed_count = 0

        # 1. Reconcile in-flight PROCESSING tasks
        in_flight = self.schedule_repo.get_in_flight_processing_records()
        for schedule in in_flight:
            if schedule.publish_record_id:
                pub_record = self.publish_repo.get_by_id(schedule.publish_record_id)
                if pub_record and pub_record.status == PublishStatus.PUBLISHED:
                    schedule.mark_published(schedule.publish_record_id)
                    self.schedule_repo.save(schedule)
                    reconciled_in_flight_count += 1
                    continue

            # In other cases, pause for safety
            schedule.mark_paused(
                error_code="SERVER_RESTARTED",
                error_message="Sunucu yeniden başlatıldığı için yayınlama işlemi duraklatıldı. Güvenle devam ettirebilirsiniz.",
            )
            self.schedule_repo.save(schedule)
            reconciled_in_flight_count += 1

        # 2. Reconcile missed SCHEDULED tasks (due time passed while offline beyond grace period)
        # Fetch due tasks
        due_candidates = self.schedule_repo.get_due_records(now_utc=now_utc, limit=500)
        cutoff_time = now_utc - timedelta(minutes=self.grace_period_minutes)

        for schedule in due_candidates:
            if schedule.scheduled_at_utc < cutoff_time:
                minutes_late = int((now_utc - schedule.scheduled_at_utc).total_seconds() / 60)
                schedule.mark_missed(
                    reason=f"Planlanan yayın zamanı uygulama çevrimdışıyken ({minutes_late} dakika önce) aşıldı. Lütfen yeni bir saat belirleyin veya yayını onaylayın."
                )
                self.schedule_repo.save(schedule)
                marked_missed_count += 1

        return reconciled_in_flight_count, marked_missed_count
