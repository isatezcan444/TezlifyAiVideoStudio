from abc import ABC, abstractmethod
from typing import List, Optional
from tezlify_studio.domain.entities.studio_asset import StudioAsset
from tezlify_studio.domain.enums.studio_status import AssetCategory

class StudioAssetRepositoryPort(ABC):
    @abstractmethod
    def save(self, asset: StudioAsset) -> StudioAsset:
        pass

    @abstractmethod
    def get_by_id(self, asset_id: str) -> Optional[StudioAsset]:
        pass

    @abstractmethod
    def list_assets(
        self,
        category: Optional[AssetCategory] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StudioAsset]:
        pass

    @abstractmethod
    def count(self, category: Optional[AssetCategory] = None) -> int:
        pass

    @abstractmethod
    def delete(self, asset_id: str) -> bool:
        pass
