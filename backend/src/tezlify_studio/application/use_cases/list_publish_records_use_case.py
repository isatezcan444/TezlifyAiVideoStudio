from typing import List, Optional
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO, PublishListResponseDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto

class ListPublishRecordsUseCase:
    def __init__(self, publish_repo: PublishRecordRepositoryPort):
        self.publish_repo = publish_repo

    def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> PublishListResponseDTO:
        records = self.publish_repo.list_all(
            limit=limit, offset=offset, channel_id=channel_id
        )
        total = self.publish_repo.count(channel_id=channel_id)
        return PublishListResponseDTO(
            items=[publish_record_to_dto(r) for r in records],
            total=total,
        )
