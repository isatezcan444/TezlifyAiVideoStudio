from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SaveCompositionRequest(BaseModel):
    composition: Dict[str, Any] = Field(..., description="VideoComposition JSON")


class StartCompositionRenderRequest(BaseModel):
    composition: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional inline composition. Saved composition is used when omitted.",
    )
    engine_override: Optional[str] = Field(
        default=None,
        pattern="^(BLENDER_WORKBENCH|BLENDER_EEVEE|workbench|eevee)$",
    )
    synthesize_voices: Optional[bool] = Field(default=True)


class CompositionTimelineEntryResponse(BaseModel):
    scene_id: str
    order: int
    duration_seconds: float
    start_time: float
    end_time: float
    transition: str
    transition_duration_seconds: float


class CompositionSummaryResponse(BaseModel):
    composition: Dict[str, Any]
    timeline: List[CompositionTimelineEntryResponse]
    total_duration_seconds: float
    scene_count: int
    text_layer_count: int
    transition_count: int
    is_saved: bool = False


class CompositionRenderJobResponse(BaseModel):
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
