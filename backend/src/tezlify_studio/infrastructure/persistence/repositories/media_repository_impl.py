from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.import_record import ImportRecord
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata
from tezlify_studio.domain.enums.media_status import MediaStatus, ImportSource
from tezlify_studio.domain.exceptions.media_exceptions import DuplicateMediaException
from tezlify_studio.infrastructure.persistence.models.media_models import (
    MediaAssetModel,
    VideoMetadataModel,
    ImportRecordModel,
)

class MediaRepositoryImpl(MediaRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, model: MediaAssetModel) -> MediaAsset:
        metadata = None
        if model.metadata_relation:
            m = model.metadata_relation
            metadata = VideoMetadata(
                duration_seconds=m.duration_seconds,
                width=m.width,
                height=m.height,
                fps=m.fps,
                video_codec=m.video_codec,
                audio_codec=m.audio_codec,
                aspect_ratio=m.aspect_ratio,
                probe_source=m.probe_source,
            )

        return MediaAsset(
            id=model.id,
            filename=model.filename,
            original_filename=model.original_filename,
            file_path=model.file_path,
            file_size_bytes=model.file_size_bytes,
            mime_type=model.mime_type,
            sha256_hash=model.sha256_hash,
            status=MediaStatus(model.status),
            thumbnail_path=model.thumbnail_path,
            created_at=model.created_at,
            updated_at=model.updated_at,
            metadata=metadata,
        )

    def save(self, asset: MediaAsset) -> MediaAsset:
        model = self.db.query(MediaAssetModel).filter(MediaAssetModel.id == asset.id).first()
        if not model:
            model = MediaAssetModel(
                id=asset.id,
                filename=asset.filename,
                original_filename=asset.original_filename,
                file_path=asset.file_path,
                file_size_bytes=asset.file_size_bytes,
                mime_type=asset.mime_type,
                sha256_hash=asset.sha256_hash,
                status=asset.status.value,
                thumbnail_path=asset.thumbnail_path,
                created_at=asset.created_at,
                updated_at=asset.updated_at,
            )
            self.db.add(model)
        else:
            model.filename = asset.filename
            model.original_filename = asset.original_filename
            model.file_path = asset.file_path
            model.file_size_bytes = asset.file_size_bytes
            model.mime_type = asset.mime_type
            model.status = asset.status.value
            model.thumbnail_path = asset.thumbnail_path
            model.updated_at = asset.updated_at

        # Save or update metadata
        if asset.metadata:
            meta_model = (
                self.db.query(VideoMetadataModel)
                .filter(VideoMetadataModel.media_asset_id == asset.id)
                .first()
            )
            if not meta_model:
                meta_model = VideoMetadataModel(
                    media_asset_id=asset.id,
                    duration_seconds=asset.metadata.duration_seconds,
                    width=asset.metadata.width,
                    height=asset.metadata.height,
                    fps=asset.metadata.fps,
                    video_codec=asset.metadata.video_codec,
                    audio_codec=asset.metadata.audio_codec,
                    aspect_ratio=asset.metadata.aspect_ratio,
                    probe_source=asset.metadata.probe_source,
                )
                self.db.add(meta_model)
            else:
                meta_model.duration_seconds = asset.metadata.duration_seconds
                meta_model.width = asset.metadata.width
                meta_model.height = asset.metadata.height
                meta_model.fps = asset.metadata.fps
                meta_model.video_codec = asset.metadata.video_codec
                meta_model.audio_codec = asset.metadata.audio_codec
                meta_model.aspect_ratio = asset.metadata.aspect_ratio
                meta_model.probe_source = asset.metadata.probe_source

        try:
            self.db.commit()
            self.db.refresh(model)
            return self._to_domain(model)
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_hash(asset.sha256_hash)
            if existing:
                raise DuplicateMediaException(asset.sha256_hash, existing.id)
            raise
        except Exception:
            self.db.rollback()
            raise

    def get_by_id(self, asset_id: str) -> Optional[MediaAsset]:
        model = self.db.query(MediaAssetModel).filter(MediaAssetModel.id == asset_id).first()
        return self._to_domain(model) if model else None

    def get_by_hash(self, sha256_hash: str) -> Optional[MediaAsset]:
        model = self.db.query(MediaAssetModel).filter(MediaAssetModel.sha256_hash == sha256_hash).first()
        return self._to_domain(model) if model else None

    def list_all(self, limit: int = 100, offset: int = 0) -> List[MediaAsset]:
        models = (
            self.db.query(MediaAssetModel)
            .order_by(MediaAssetModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def count(self) -> int:
        return self.db.query(MediaAssetModel).count()

    def delete(self, asset_id: str) -> bool:
        model = self.db.query(MediaAssetModel).filter(MediaAssetModel.id == asset_id).first()
        if model:
            try:
                self.db.delete(model)
                self.db.commit()
                return True
            except Exception:
                self.db.rollback()
                raise
        return False

    def save_import_record(self, record: ImportRecord) -> ImportRecord:
        model = ImportRecordModel(
            id=record.id,
            media_asset_id=record.media_asset_id,
            source_type=record.source_type.value,
            status=record.status,
            error_message=record.error_message,
            created_at=record.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return record

