import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.domain.entities.studio_project import StudioProject
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.infrastructure.persistence.models.studio_models import StudioProjectModel

class StudioProjectRepositoryImpl(StudioProjectRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _ensure_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _to_domain(self, model: StudioProjectModel) -> StudioProject:
        scene_graph = None
        if model.scene_graph_json:
            try:
                scene_graph = SceneGraph.model_validate_json(model.scene_graph_json)
            except Exception:
                scene_graph = None

        return StudioProject(
            id=model.id,
            title=model.title,
            description=model.description or "",
            status=StudioProjectStatus(model.status),
            scene_graph=scene_graph,
            created_at=self._ensure_utc(model.created_at),
            updated_at=self._ensure_utc(model.updated_at),
        )

    def save(self, project: StudioProject) -> StudioProject:
        scene_graph_json = "{}"
        if project.scene_graph:
            scene_graph_json = project.scene_graph.model_dump_json()

        existing = self.db.query(StudioProjectModel).filter(StudioProjectModel.id == project.id).first()
        if existing:
            existing.title = project.title
            existing.description = project.description
            existing.status = project.status.value
            existing.scene_graph_json = scene_graph_json
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return self._to_domain(existing)

        new_model = StudioProjectModel(
            id=project.id,
            title=project.title,
            description=project.description,
            status=project.status.value,
            scene_graph_json=scene_graph_json,
            created_at=project.created_at or datetime.now(timezone.utc),
            updated_at=project.updated_at or datetime.now(timezone.utc),
        )
        self.db.add(new_model)
        self.db.commit()
        self.db.refresh(new_model)
        return self._to_domain(new_model)

    def get_by_id(self, project_id: str) -> Optional[StudioProject]:
        model = self.db.query(StudioProjectModel).filter(StudioProjectModel.id == project_id).first()
        return self._to_domain(model) if model else None

    def list_projects(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[StudioProjectStatus] = None,
    ) -> List[StudioProject]:
        query = self.db.query(StudioProjectModel)
        if status is not None:
            query = query.filter(StudioProjectModel.status == status.value)
        models = (
            query.order_by(desc(StudioProjectModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def count_projects(self, status: Optional[StudioProjectStatus] = None) -> int:
        query = self.db.query(StudioProjectModel)
        if status is not None:
            query = query.filter(StudioProjectModel.status == status.value)
        return query.count()

    def delete(self, project_id: str) -> bool:
        model = self.db.query(StudioProjectModel).filter(StudioProjectModel.id == project_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
