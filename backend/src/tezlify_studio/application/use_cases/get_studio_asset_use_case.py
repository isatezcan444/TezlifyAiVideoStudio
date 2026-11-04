from tezlify_studio.application.ports.studio_asset_repository_port import StudioAssetRepositoryPort
from tezlify_studio.application.dto.character_dto import StudioAssetDTO
from tezlify_studio.application.dto.mappers import studio_asset_to_dto
from tezlify_studio.domain.exceptions.studio_exceptions import AssetNotFoundException

class GetStudioAssetUseCase:
    def __init__(self, asset_repo: StudioAssetRepositoryPort):
        self.asset_repo = asset_repo

    def execute(self, asset_id: str) -> StudioAssetDTO:
        asset = self.asset_repo.get_by_id(asset_id)
        if not asset:
            raise AssetNotFoundException(asset_id)
        return studio_asset_to_dto(asset)
