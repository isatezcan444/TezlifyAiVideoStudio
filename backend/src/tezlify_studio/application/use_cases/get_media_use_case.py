from typing import Optional
from tezlify_studio.domain.exceptions.media_exceptions import EntityNotFoundException
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.dto.media_dto import MediaAssetDTO
from tezlify_studio.application.dto.mappers import media_asset_to_dto

class GetMediaUseCase:
    def __init__(self, repository: MediaRepositoryPort):
        self.repository = repository

    def execute(self, media_id: str) -> MediaAssetDTO:
        asset = self.repository.get_by_id(media_id)
        if not asset:
            raise EntityNotFoundException("MediaAsset", media_id)
        return media_asset_to_dto(asset)

