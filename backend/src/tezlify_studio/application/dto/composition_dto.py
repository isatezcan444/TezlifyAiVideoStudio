from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CompositionTimelineEntryDTO(BaseModel):
    scene_id: str
    order: int
    duration_seconds: float
    start_time: float
    end_time: float
    transition: str
    transition_duration_seconds: float


class CompositionSummaryDTO(BaseModel):
    composition: Dict[str, Any]
    timeline: List[CompositionTimelineEntryDTO]
    total_duration_seconds: float
    scene_count: int
    text_layer_count: int
    transition_count: int
    is_saved: bool = False


class StartCompositionRenderRequestDTO(BaseModel):
    project_id: str
    composition: Optional[Dict[str, Any]] = None
    engine_override: Optional[str] = None
    synthesize_voices: bool = True
