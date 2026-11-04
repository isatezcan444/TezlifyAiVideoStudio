from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class StartRenderRequest(BaseModel):
    engine_override: Optional[str] = Field(None, pattern="^(BLENDER_WORKBENCH|BLENDER_EEVEE|workbench|eevee)$")

class RenderJobResponse(BaseModel):
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

class RenderJobListResponse(BaseModel):
    items: List[RenderJobResponse]
    total: int
