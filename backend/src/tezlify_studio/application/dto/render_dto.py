from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from tezlify_studio.domain.entities.render_job import RenderJob

class StartRenderRequestDTO(BaseModel):
    project_id: str
    engine_override: Optional[str] = None

class RenderJobDTO(BaseModel):
    id: str
    project_id: str
    status: str
    progress_percent: float
    current_step: str
    output_video_path: Optional[str] = None
    output_metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @classmethod
    def from_entity(cls, entity: RenderJob) -> "RenderJobDTO":
        meta_dict = None
        if entity.output_metadata:
            meta_dict = entity.output_metadata.model_dump()

        return cls(
            id=entity.id,
            project_id=entity.project_id,
            status=entity.status.value,
            progress_percent=entity.progress_percent,
            current_step=entity.current_step,
            output_video_path=entity.output_video_path,
            output_metadata=meta_dict,
            error_message=entity.error_message,
            created_at=entity.created_at.isoformat() if entity.created_at else "",
            started_at=entity.started_at.isoformat() if entity.started_at else None,
            completed_at=entity.completed_at.isoformat() if entity.completed_at else None,
        )
