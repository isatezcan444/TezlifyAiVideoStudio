from typing import List
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.dto.media_dto import MediaListResponseDTO
from tezlify_studio.application.dto.mappers import media_asset_to_dto

class ListMediaUseCase:
    def __init__(self, repository: MediaRepositoryPort):
        self.repository = repository

    def execute(self, limit: int = 100, offset: int = 0) -> MediaListResponseDTO:
        assets = self.repository.list_all(limit=limit, offset=offset)
        total = self.repository.count()
        return MediaListResponseDTO(
            items=[media_asset_to_dto(a) for a in assets],
            total=total,
        )
