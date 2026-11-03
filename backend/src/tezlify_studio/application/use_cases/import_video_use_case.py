import os
import uuid
import re
from typing import BinaryIO
from datetime import datetime, timezone
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.import_record import ImportRecord
from tezlify_studio.domain.enums.media_status import MediaStatus, ImportSource
from tezlify_studio.domain.exceptions.media_exceptions import (
    InvalidMediaFileException,
    DuplicateMediaException,
)
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort
from tezlify_studio.application.ports.video_probe_port import VideoProbePort
from tezlify_studio.application.dto.media_dto import MediaAssetDTO
from tezlify_studio.application.dto.mappers import media_asset_to_dto

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ALLOWED_MIME_PREFIXES = ("video/", "application/octet-stream")

class ImportVideoUseCase:
    def __init__(
        self,
        repository: MediaRepositoryPort,
        storage: MediaStoragePort,
        probe: VideoProbePort,
        max_upload_bytes: Optional[int] = None,
    ):
        self.repository = repository
        self.storage = storage
        self.probe = probe
        self.max_upload_bytes = max_upload_bytes

    def execute(
        self,
        stream: BinaryIO,
        original_filename: str,
        content_type: str,
    ) -> MediaAssetDTO:
        # 1. Sanitize original filename and check extension
        clean_name = os.path.basename(original_filename.strip())
        _, ext = os.path.splitext(clean_name.lower())

        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidMediaFileException(
                f"Desteklenmeyen video formatı: '{ext}'. İzin verilen formatlar: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # 2. Generate safe internal filename
        asset_id = str(uuid.uuid4())
        safe_base = re.sub(r'[^a-zA-Z0-9_\-]', '_', os.path.splitext(clean_name)[0])[:40]
        stored_filename = f"{asset_id}_{safe_base}{ext}"

        # 3. Stream to storage, compute sha256 and size on the fly
        file_path, file_size, sha256_hash = self.storage.save_stream(
            stream=stream,
            destination_filename=stored_filename,
            max_bytes=self.max_upload_bytes,
        )

        try:
            # 4. Check for duplicate SHA-256 hash in database
            existing = self.repository.get_by_hash(sha256_hash)
            if existing:
                raise DuplicateMediaException(sha256_hash, existing.id)

            # 5. Extract video metadata
            metadata = self.probe.probe_video(file_path)

            # 6. Attempt thumbnail generation if possible
            thumb_filename = f"thumb_{asset_id}.jpg"
            thumb_dest = os.path.join(os.path.dirname(file_path), thumb_filename)
            thumbnail_path = self.probe.generate_thumbnail(file_path, thumb_dest)

            # 7. Create MediaAsset entity
            asset = MediaAsset(
                id=asset_id,
                filename=stored_filename,
                original_filename=clean_name,
                file_path=file_path,
                file_size_bytes=file_size,
                mime_type=content_type or f"video/{ext.lstrip('.')}",
                sha256_hash=sha256_hash,
                status=MediaStatus.READY,
                thumbnail_path=thumbnail_path,
                metadata=metadata,
            )

            saved_asset = self.repository.save(asset)

            # 8. Create ImportRecord
            import_record = ImportRecord(
                id=str(uuid.uuid4()),
                media_asset_id=asset.id,
                source_type=ImportSource.MANUAL_UPLOAD,
                status="success",
            )
            self.repository.save_import_record(import_record)

            return media_asset_to_dto(saved_asset)

        except Exception:
            # Clean up permanent file and thumbnail if anything fails downstream
            if self.storage.exists(file_path):
                self.storage.delete_file(file_path)
            thumb_path = os.path.join(os.path.dirname(file_path), f"thumb_{asset_id}.jpg")
            if self.storage.exists(thumb_path):
                self.storage.delete_file(thumb_path)
            raise

