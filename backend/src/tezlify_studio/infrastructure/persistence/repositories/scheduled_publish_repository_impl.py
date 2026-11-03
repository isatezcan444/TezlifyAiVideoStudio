import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus
from tezlify_studio.infrastructure.persistence.models.schedule_models import ScheduledPublishModel

class ScheduledPublishRepositoryImpl(ScheduledPublishRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _ensure_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _to_domain(self, model: ScheduledPublishModel) -> ScheduledPublish:
        try:
            tags = json.loads(model.tags_json) if model.tags_json else []
        except Exception:
            tags = []

        return ScheduledPublish(
            id=model.id,
            media_asset_id=model.media_asset_id,
            social_account_id=model.social_account_id,
            platform=SocialPlatform(model.platform),
            title=model.title,
            description=model.description,
            tags=tags,
            privacy_status=PrivacyStatus(model.privacy_status),
            scheduled_at_utc=self._ensure_utc(model.scheduled_at_utc),
            timezone=model.timezone,
            status=ScheduleStatus(model.status),
            publish_record_id=model.publish_record_id,
            attempt_count=model.attempt_count,
            max_attempts=model.max_attempts,
            last_error_code=model.last_error_code,
            last_error_message=model.last_error_message,
            started_at=self._ensure_utc(model.started_at),
            completed_at=self._ensure_utc(model.completed_at),
            created_at=self._ensure_utc(model.created_at),
            updated_at=self._ensure_utc(model.updated_at),
            version=model.version,
        )

    def save(self, record: ScheduledPublish) -> ScheduledPublish:
        model = (
            self.db.query(ScheduledPublishModel)
            .filter(ScheduledPublishModel.id == record.id)
            .first()
        )
        tags_str = json.dumps(record.tags if record.tags else [])

        # SQLite stores naive datetimes; convert to UTC naive for DB compatibility
        sched_naive = record.scheduled_at_utc.astimezone(timezone.utc).replace(tzinfo=None)
        started_naive = (
            record.started_at.astimezone(timezone.utc).replace(tzinfo=None)
            if record.started_at
            else None
        )
        completed_naive = (
            record.completed_at.astimezone(timezone.utc).replace(tzinfo=None)
            if record.completed_at
            else None
        )
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        if not model:
            model = ScheduledPublishModel(
                id=record.id,
                media_asset_id=record.media_asset_id,
                social_account_id=record.social_account_id,
                platform=record.platform.value,
                title=record.title,
                description=record.description,
                tags_json=tags_str,
                privacy_status=record.privacy_status.value,
                scheduled_at_utc=sched_naive,
                timezone=record.timezone,
                status=record.status.value,
                publish_record_id=record.publish_record_id,
                attempt_count=record.attempt_count,
                max_attempts=record.max_attempts,
                last_error_code=record.last_error_code,
                last_error_message=record.last_error_message,
                started_at=started_naive,
                completed_at=completed_naive,
                created_at=record.created_at.astimezone(timezone.utc).replace(tzinfo=None),
                updated_at=now_naive,
                version=record.version,
            )
            self.db.add(model)
        else:
            model.media_asset_id = record.media_asset_id
            model.social_account_id = record.social_account_id
            model.platform = record.platform.value
            model.title = record.title
            model.description = record.description
            model.tags_json = tags_str
            model.privacy_status = record.privacy_status.value
            model.scheduled_at_utc = sched_naive
            model.timezone = record.timezone
            model.status = record.status.value
            model.publish_record_id = record.publish_record_id
            model.attempt_count = record.attempt_count
            model.max_attempts = record.max_attempts
            model.last_error_code = record.last_error_code
            model.last_error_message = record.last_error_message
            model.started_at = started_naive
            model.completed_at = completed_naive
            model.updated_at = now_naive
            model.version = record.version

        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, schedule_id: str) -> Optional[ScheduledPublish]:
        model = (
            self.db.query(ScheduledPublishModel)
            .filter(ScheduledPublishModel.id == schedule_id)
            .first()
        )
        return self._to_domain(model) if model else None

    def get_due_records(self, now_utc: datetime, limit: int = 10) -> List[ScheduledPublish]:
        naive_now = now_utc.astimezone(timezone.utc).replace(tzinfo=None)
        models = (
            self.db.query(ScheduledPublishModel)
            .filter(
                ScheduledPublishModel.status == ScheduleStatus.SCHEDULED.value,
                ScheduledPublishModel.scheduled_at_utc <= naive_now,
            )
            .order_by(ScheduledPublishModel.scheduled_at_utc.asc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def get_in_flight_processing_records(self) -> List[ScheduledPublish]:
        models = (
            self.db.query(ScheduledPublishModel)
            .filter(ScheduledPublishModel.status == ScheduleStatus.PROCESSING.value)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def get_active_by_media(
        self,
        media_id: str,
        platform: SocialPlatform,
    ) -> Optional[ScheduledPublish]:
        active_statuses = [
            ScheduleStatus.SCHEDULED.value,
            ScheduleStatus.PROCESSING.value,
            ScheduleStatus.PAUSED.value,
        ]
        model = (
            self.db.query(ScheduledPublishModel)
            .filter(
                ScheduledPublishModel.media_asset_id == media_id,
                ScheduledPublishModel.platform == platform.value,
                ScheduledPublishModel.status.in_(active_statuses),
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def list_all(
        self,
        status: Optional[ScheduleStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ScheduledPublish]:
        query = self.db.query(ScheduledPublishModel)
        if status:
            query = query.filter(ScheduledPublishModel.status == status.value)
        models = (
            query.order_by(ScheduledPublishModel.scheduled_at_utc.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def list_upcoming(self, now_utc: datetime, limit: int = 20) -> List[ScheduledPublish]:
        naive_now = now_utc.astimezone(timezone.utc).replace(tzinfo=None)
        models = (
            self.db.query(ScheduledPublishModel)
            .filter(
                ScheduledPublishModel.status == ScheduleStatus.SCHEDULED.value,
                ScheduledPublishModel.scheduled_at_utc >= naive_now,
            )
            .order_by(ScheduledPublishModel.scheduled_at_utc.asc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def claim_for_processing(self, schedule_id: str, expected_version: int) -> bool:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        updated_rows = (
            self.db.query(ScheduledPublishModel)
            .filter(
                ScheduledPublishModel.id == schedule_id,
                ScheduledPublishModel.version == expected_version,
                ScheduledPublishModel.status == ScheduleStatus.SCHEDULED.value,
            )
            .update(
                {
                    ScheduledPublishModel.status: ScheduleStatus.PROCESSING.value,
                    ScheduledPublishModel.version: ScheduledPublishModel.version + 1,
                    ScheduledPublishModel.started_at: now_naive,
                    ScheduledPublishModel.attempt_count: ScheduledPublishModel.attempt_count + 1,
                    ScheduledPublishModel.updated_at: now_naive,
                },
                synchronize_session="fetch",
            )
        )
        self.db.commit()
        return updated_rows > 0

    def count(self, status: Optional[ScheduleStatus] = None) -> int:
        query = self.db.query(ScheduledPublishModel)
        if status:
            query = query.filter(ScheduledPublishModel.status == status.value)
        return query.count()

    def delete(self, schedule_id: str) -> bool:
        model = (
            self.db.query(ScheduledPublishModel)
            .filter(ScheduledPublishModel.id == schedule_id)
            .first()
        )
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
