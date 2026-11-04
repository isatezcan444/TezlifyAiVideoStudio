from typing import List, Tuple, Optional
from tezlify_studio.application.ports.studio_asset_repository_port import StudioAssetRepositoryPort
from tezlify_studio.application.dto.character_dto import StudioAssetDTO
from tezlify_studio.application.dto.mappers import studio_asset_to_dto
from tezlify_studio.domain.enums.studio_status import AssetCategory

class ListStudioAssetsUseCase:
    def __init__(self, asset_repo: StudioAssetRepositoryPort):
        self.asset_repo = asset_repo

    def execute(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[StudioAssetDTO], int]:
        cat_enum = AssetCategory(category) if category else None
        total = self.asset_repo.count(category=cat_enum)
        assets = self.asset_repo.list_assets(
            category=cat_enum,
            limit=limit,
            offset=offset,
        )
        return [studio_asset_to_dto(a) for a in assets], total
