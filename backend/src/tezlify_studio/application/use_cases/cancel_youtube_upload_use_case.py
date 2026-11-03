from tezlify_studio.domain.enums.publish_status import PublishStatus
from tezlify_studio.domain.exceptions.media_exceptions import EntityNotFoundException, InvalidMediaFileException
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto

class CancelYouTubeUploadUseCase:
    def __init__(self, publish_repo: PublishRecordRepositoryPort):
        self.publish_repo = publish_repo

    def execute(self, publish_id: str) -> PublishRecordDTO:
        record = self.publish_repo.get_by_id(publish_id)
        if not record:
            raise EntityNotFoundException("PublishRecord", publish_id)

        if record.status == PublishStatus.PUBLISHED:
            raise InvalidMediaFileException("Tamamlanmış ve YouTube'da yayınlanmış bir video iptal edilemez.")

        record.transition_to(PublishStatus.CANCELLED, error_code="USER_CANCELLED", error_message="İşlem kullanıcı tarafından iptal edildi.")
        saved = self.publish_repo.save(record)
        return publish_record_to_dto(saved)
