from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from tezlify_studio.application.ports.composition_repository_port import (
    CompositionRepositoryPort,
)
from tezlify_studio.domain.value_objects.video_composition import VideoComposition
from tezlify_studio.infrastructure.persistence.models.studio_models import (
    VideoCompositionModel,
)


class CompositionRepositoryImpl(CompositionRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def save(self, composition: VideoComposition) -> VideoComposition:
        existing = (
            self.db.query(VideoCompositionModel)
            .filter(VideoCompositionModel.project_id == composition.project_id)
            .first()
        )
        payload = composition.model_dump_json()

        if existing:
            existing.id = composition.id
            existing.name = composition.name
            existing.composition_json = payload
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return VideoComposition.model_validate_json(existing.composition_json)

        model = VideoCompositionModel(
            id=composition.id,
            project_id=composition.project_id,
            name=composition.name,
            composition_json=payload,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return VideoComposition.model_validate_json(model.composition_json)

    def get_by_project_id(self, project_id: str) -> Optional[VideoComposition]:
        model = (
            self.db.query(VideoCompositionModel)
            .filter(VideoCompositionModel.project_id == project_id)
            .first()
        )
        if not model:
            return None
        try:
            return VideoComposition.model_validate_json(model.composition_json)
        except Exception:
            return None

    def delete_by_project_id(self, project_id: str) -> bool:
        model = (
            self.db.query(VideoCompositionModel)
            .filter(VideoCompositionModel.project_id == project_id)
            .first()
        )
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
