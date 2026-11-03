from typing import List, Optional
import json
from sqlalchemy.orm import Session
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.infrastructure.persistence.models.publish_models import PublishRecordModel

class PublishRecordRepositoryImpl(PublishRecordRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, model: PublishRecordModel) -> PublishRecord:
        try:
            tags = json.loads(model.tags_json) if model.tags_json else []
        except Exception:
            tags = []

        return PublishRecord(
            id=model.id,
            media_asset_id=model.media_asset_id,
            platform=SocialPlatform(model.platform),
            external_video_id=model.external_video_id,
            external_video_url=model.external_video_url,
            title=model.title,
            description=model.description,
            tags=tags,
            category_id=model.category_id,
            privacy_status=PrivacyStatus(model.privacy_status),
            status=PublishStatus(model.status),
            progress_percentage=model.progress_percentage,
            uploaded_bytes=model.uploaded_bytes,
            total_bytes=model.total_bytes,
            upload_session_uri=model.upload_session_uri,
            thumbnail_path=model.thumbnail_path,
            error_code=model.error_code,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            published_at=model.published_at,
        )

    def save(self, record: PublishRecord) -> PublishRecord:
        model = self.db.query(PublishRecordModel).filter(PublishRecordModel.id == record.id).first()
        tags_str = json.dumps(record.tags if record.tags else [])

        if not model:
            model = PublishRecordModel(
                id=record.id,
                media_asset_id=record.media_asset_id,
                platform=record.platform.value,
                external_video_id=record.external_video_id,
                external_video_url=record.external_video_url,
                title=record.title,
                description=record.description,
                tags_json=tags_str,
                category_id=record.category_id,
                privacy_status=record.privacy_status.value,
                status=record.status.value,
                progress_percentage=record.progress_percentage,
                uploaded_bytes=record.uploaded_bytes,
                total_bytes=record.total_bytes,
                upload_session_uri=record.upload_session_uri,
                thumbnail_path=record.thumbnail_path,
                error_code=record.error_code,
                error_message=record.error_message,
                created_at=record.created_at,
                updated_at=record.updated_at,
                published_at=record.published_at,
            )
            self.db.add(model)
        else:
            model.platform = record.platform.value
            model.external_video_id = record.external_video_id
            model.external_video_url = record.external_video_url
            model.title = record.title
            model.description = record.description
            model.tags_json = tags_str
            model.category_id = record.category_id
            model.privacy_status = record.privacy_status.value
            model.status = record.status.value
            model.progress_percentage = record.progress_percentage
            model.uploaded_bytes = record.uploaded_bytes
            model.total_bytes = record.total_bytes
            model.upload_session_uri = record.upload_session_uri
            model.thumbnail_path = record.thumbnail_path
            model.error_code = record.error_code
            model.error_message = record.error_message
            model.updated_at = record.updated_at
            model.published_at = record.published_at

        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, record_id: str) -> Optional[PublishRecord]:
        model = self.db.query(PublishRecordModel).filter(PublishRecordModel.id == record_id).first()
        return self._to_domain(model) if model else None

    def get_active_by_media(self, media_id: str, platform: SocialPlatform) -> Optional[PublishRecord]:
        # Active means in progress (pending, authenticating, uploading, paused, processing)
        active_statuses = [
            PublishStatus.PENDING.value,
            PublishStatus.AUTHENTICATING.value,
            PublishStatus.UPLOADING.value,
            PublishStatus.PAUSED.value,
            PublishStatus.PROCESSING.value,
        ]
        model = (
            self.db.query(PublishRecordModel)
            .filter(
                PublishRecordModel.media_asset_id == media_id,
                PublishRecordModel.platform == platform.value,
                PublishRecordModel.status.in_(active_statuses),
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def get_latest_by_media(self, media_id: str, platform: SocialPlatform) -> Optional[PublishRecord]:
        model = (
            self.db.query(PublishRecordModel)
            .filter(
                PublishRecordModel.media_asset_id == media_id,
                PublishRecordModel.platform == platform.value,
            )
            .order_by(PublishRecordModel.created_at.desc())
            .first()
        )
        return self._to_domain(model) if model else None

    def list_by_platform(self, platform: SocialPlatform, limit: int = 50, offset: int = 0) -> List[PublishRecord]:
        models = (
            self.db.query(PublishRecordModel)
            .filter(PublishRecordModel.platform == platform.value)
            .order_by(PublishRecordModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def list_all(self, limit: int = 50, offset: int = 0) -> List[PublishRecord]:
        models = (
            self.db.query(PublishRecordModel)
            .order_by(PublishRecordModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def get_in_flight_records(self) -> List[PublishRecord]:
        in_flight = [
            PublishStatus.PENDING.value,
            PublishStatus.AUTHENTICATING.value,
            PublishStatus.UPLOADING.value,
        ]
        models = (
            self.db.query(PublishRecordModel)
            .filter(PublishRecordModel.status.in_(in_flight))
            .all()
        )
        return [self._to_domain(m) for m in models]

    def count(self) -> int:
        return self.db.query(PublishRecordModel).count()

    def delete(self, record_id: str) -> bool:
        model = self.db.query(PublishRecordModel).filter(PublishRecordModel.id == record_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
