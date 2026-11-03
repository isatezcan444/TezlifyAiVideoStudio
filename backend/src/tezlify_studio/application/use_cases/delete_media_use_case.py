from tezlify_studio.domain.exceptions.media_exceptions import EntityNotFoundException
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort

class DeleteMediaUseCase:
    def __init__(
        self,
        repository: MediaRepositoryPort,
        storage: MediaStoragePort,
    ):
        self.repository = repository
        self.storage = storage

    def execute(self, media_id: str) -> bool:
        asset = self.repository.get_by_id(media_id)
        if not asset:
            raise EntityNotFoundException("MediaAsset", media_id)

        # 1. Remove record from database first (if DB fails, files remain intact)
        deleted = self.repository.delete(media_id)

        # 2. Clean up physical files on disk
        if deleted:
            if asset.file_path and self.storage.exists(asset.file_path):
                self.storage.delete_file(asset.file_path)

            if asset.thumbnail_path and self.storage.exists(asset.thumbnail_path):
                self.storage.delete_file(asset.thumbnail_path)

        return deleted

