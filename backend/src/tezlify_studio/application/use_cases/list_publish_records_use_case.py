from typing import List
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO, PublishListResponseDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto

class ListPublishRecordsUseCase:
    def __init__(self, publish_repo: PublishRecordRepositoryPort):
        self.publish_repo = publish_repo

    def execute(self, limit: int = 50, offset: int = 0) -> PublishListResponseDTO:
        records = self.publish_repo.list_all(limit=limit, offset=offset)
        total = self.publish_repo.count()
        return PublishListResponseDTO(
            items=[publish_record_to_dto(r) for r in records],
            total=total,
        )
