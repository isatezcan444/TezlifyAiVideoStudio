from typing import List
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.domain.enums.publish_status import PublishStatus
from tezlify_studio.domain.entities.publish_record import PublishRecord

class ReconcilePublishRecordsUseCase:
    """
    On application startup, reconciles any publishing jobs left in non-terminal/in-flight
    states (PENDING, AUTHENTICATING, UPLOADING) caused by server restart or process termination.
    Transitions them to PAUSED with error_code='SERVER_RESTARTED' so they can be resumed cleanly.
    """
    def __init__(self, publish_repo: PublishRecordRepositoryPort):
        self.publish_repo = publish_repo

    def execute(self) -> List[PublishRecord]:
        in_flight = self.publish_repo.get_in_flight_records()
        reconciled = []
        for record in in_flight:
            record.transition_to(
                PublishStatus.PAUSED,
                error_code="SERVER_RESTARTED",
                error_message="Sunucu yeniden başlatıldığı için yükleme duraklatıldı. Kaldığı yerden devam ettirebilirsiniz.",
            )
            saved = self.publish_repo.save(record)
            reconciled.append(saved)
        return reconciled
