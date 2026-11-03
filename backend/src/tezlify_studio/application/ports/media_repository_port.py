from abc import ABC, abstractmethod
from typing import List, Optional
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.import_record import ImportRecord

class MediaRepositoryPort(ABC):
    @abstractmethod
    def save(self, asset: MediaAsset) -> MediaAsset:
        pass

    @abstractmethod
    def get_by_id(self, asset_id: str) -> Optional[MediaAsset]:
        pass

    @abstractmethod
    def get_by_hash(self, sha256_hash: str) -> Optional[MediaAsset]:
        pass

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[MediaAsset]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def delete(self, asset_id: str) -> bool:
        pass

    @abstractmethod
    def save_import_record(self, record: ImportRecord) -> ImportRecord:
        pass

