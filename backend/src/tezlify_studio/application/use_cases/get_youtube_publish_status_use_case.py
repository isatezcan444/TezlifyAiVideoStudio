from tezlify_studio.domain.exceptions.media_exceptions import EntityNotFoundException
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto

class GetYouTubePublishStatusUseCase:
    def __init__(self, publish_repo: PublishRecordRepositoryPort):
        self.publish_repo = publish_repo

    def execute(self, publish_id: str) -> PublishRecordDTO:
        record = self.publish_repo.get_by_id(publish_id)
        if not record:
            raise EntityNotFoundException("PublishRecord", publish_id)
        return publish_record_to_dto(record)
