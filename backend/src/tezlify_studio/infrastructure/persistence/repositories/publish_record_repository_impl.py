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
            channel_id=model.channel_id,
            platform_connection_id=model.platform_connection_id,
            channel_attribution=model.channel_attribution or "unresolved",
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
                channel_id=record.channel_id,
                platform_connection_id=record.platform_connection_id,
                channel_attribution=record.channel_attribution,
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
            model.channel_id = record.channel_id
            model.platform_connection_id = record.platform_connection_id
            model.channel_attribution = record.channel_attribution
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

    def get_active_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[PublishRecord]:
        # Active means in progress (pending, authenticating, uploading, paused, processing)
        active_statuses = [
            PublishStatus.PENDING.value,
            PublishStatus.AUTHENTICATING.value,
            PublishStatus.UPLOADING.value,
            PublishStatus.PAUSED.value,
            PublishStatus.PROCESSING.value,
        ]
        query = self.db.query(PublishRecordModel).filter(
            PublishRecordModel.media_asset_id == media_id,
            PublishRecordModel.platform == platform.value,
            PublishRecordModel.status.in_(active_statuses),
        )
        if channel_id:
            query = query.filter(PublishRecordModel.channel_id == channel_id)
        model = query.first()
        return self._to_domain(model) if model else None

    def get_latest_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[PublishRecord]:
        query = self.db.query(PublishRecordModel).filter(
            PublishRecordModel.media_asset_id == media_id,
            PublishRecordModel.platform == platform.value,
        )
        if channel_id:
            query = query.filter(PublishRecordModel.channel_id == channel_id)
        model = query.order_by(PublishRecordModel.created_at.desc()).first()
        return self._to_domain(model) if model else None

    def list_by_platform(
        self,
        platform: SocialPlatform,
        limit: int = 50,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> List[PublishRecord]:
        query = self.db.query(PublishRecordModel).filter(
            PublishRecordModel.platform == platform.value
        )
        if channel_id:
            query = query.filter(PublishRecordModel.channel_id == channel_id)
        models = (
            query.order_by(PublishRecordModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def count_by_channel(self, channel_id: str) -> int:
        return (
            self.db.query(PublishRecordModel)
            .filter(PublishRecordModel.channel_id == channel_id)
            .count()
        )

    def fail_pending_for_connection(
        self, connection_id: str, error_code: str, error_message: str
    ) -> int:
        pending = [
            PublishStatus.PENDING.value,
            PublishStatus.AUTHENTICATING.value,
            PublishStatus.UPLOADING.value,
            PublishStatus.PAUSED.value,
            PublishStatus.PROCESSING.value,
        ]
        models = (
            self.db.query(PublishRecordModel)
            .filter(
                PublishRecordModel.platform_connection_id == connection_id,
                PublishRecordModel.status.in_(pending),
            )
            .all()
        )
        for model in models:
            model.status = PublishStatus.FAILED.value
            model.error_code = error_code
            model.error_message = error_message
        self.db.commit()
        return len(models)

    def list_all(
        self, limit: int = 50, offset: int = 0, channel_id: Optional[str] = None
    ) -> List[PublishRecord]:
        query = self.db.query(PublishRecordModel)
        if channel_id:
            query = query.filter(PublishRecordModel.channel_id == channel_id)
        models = (
            query.order_by(PublishRecordModel.created_at.desc())
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

    def count(self, channel_id: Optional[str] = None) -> int:
        query = self.db.query(PublishRecordModel)
        if channel_id:
            query = query.filter(PublishRecordModel.channel_id == channel_id)
        return query.count()

    def delete(self, record_id: str) -> bool:
        model = self.db.query(PublishRecordModel).filter(PublishRecordModel.id == record_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
