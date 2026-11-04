from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from tezlify_studio.application.ports.render_job_repository_port import RenderJobRepositoryPort
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.infrastructure.persistence.models.studio_models import RenderJobModel

class RenderJobRepositoryImpl(RenderJobRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _ensure_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _to_domain(self, model: RenderJobModel) -> RenderJob:
        output_metadata = None
        if model.output_metadata_json:
            try:
                output_metadata = RenderOutputMetadata.model_validate_json(model.output_metadata_json)
            except Exception:
                output_metadata = None

        return RenderJob(
            id=model.id,
            project_id=model.project_id,
            status=RenderJobStatus(model.status),
            progress_percent=float(model.progress_percent or 0.0),
            current_step=model.current_step or "Pending",
            output_video_path=model.output_video_path,
            output_metadata=output_metadata,
            error_message=model.error_message,
            created_at=self._ensure_utc(model.created_at) or datetime.now(timezone.utc),
            started_at=self._ensure_utc(model.started_at),
            completed_at=self._ensure_utc(model.completed_at),
        )

    def save(self, job: RenderJob) -> RenderJob:
        meta_json = None
        if job.output_metadata:
            meta_json = job.output_metadata.model_dump_json()

        existing = self.db.query(RenderJobModel).filter(RenderJobModel.id == job.id).first()
        if existing:
            existing.status = job.status.value
            existing.progress_percent = job.progress_percent
            existing.current_step = job.current_step
            existing.output_video_path = job.output_video_path
            existing.output_metadata_json = meta_json
            existing.error_message = job.error_message
            existing.started_at = job.started_at
            existing.completed_at = job.completed_at
            self.db.commit()
            self.db.refresh(existing)
            return self._to_domain(existing)

        new_model = RenderJobModel(
            id=job.id,
            project_id=job.project_id,
            status=job.status.value,
            progress_percent=job.progress_percent,
            current_step=job.current_step,
            output_video_path=job.output_video_path,
            output_metadata_json=meta_json,
            error_message=job.error_message,
            created_at=job.created_at or datetime.now(timezone.utc),
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
        self.db.add(new_model)
        self.db.commit()
        self.db.refresh(new_model)
        return self._to_domain(new_model)

    def get_by_id(self, job_id: str) -> Optional[RenderJob]:
        model = self.db.query(RenderJobModel).filter(RenderJobModel.id == job_id).first()
        if not model:
            return None
        return self._to_domain(model)

    def list_by_project_id(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RenderJob]:
        models = (
            self.db.query(RenderJobModel)
            .filter(RenderJobModel.project_id == project_id)
            .order_by(desc(RenderJobModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def list_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[RenderJobStatus] = None,
    ) -> List[RenderJob]:
        query = self.db.query(RenderJobModel)
        if status:
            query = query.filter(RenderJobModel.status == status.value)
        models = query.order_by(desc(RenderJobModel.created_at)).offset(offset).limit(limit).all()
        return [self._to_domain(m) for m in models]

    def count_jobs(
        self,
        status: Optional[RenderJobStatus] = None,
    ) -> int:
        query = self.db.query(RenderJobModel)
        if status:
            query = query.filter(RenderJobModel.status == status.value)
        return int(query.count())

    def delete(self, job_id: str) -> bool:
        model = self.db.query(RenderJobModel).filter(RenderJobModel.id == job_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
