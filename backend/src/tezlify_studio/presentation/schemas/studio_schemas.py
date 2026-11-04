from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class CreateStudioProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Project title")
    description: Optional[str] = Field(default="", max_length=2000, description="Project description")
    scene_graph: Optional[Dict[str, Any]] = Field(default=None, description="Pre-generated SceneGraph dictionary")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Proje başlığı boş olamaz.")
        return v.strip()

class UpdateStudioProjectRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, pattern="^(draft|scenario_ready|render_queued|rendering|completed|failed|archived)$")
    scene_graph: Optional[Dict[str, Any]] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Proje başlığı boş olamaz.")
        return v.strip() if v is not None else None

class GenerateStoryRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1500, description="Creative description / prompt for the animation")
    target_duration_seconds: Optional[float] = Field(default=30.0, ge=5.0, le=300.0, description="Target animation duration in seconds")
    aspect_ratio: Optional[str] = Field(default="16:9", pattern="^(16:9|9:16|1:1)$")
    genre: Optional[str] = Field(default=None, pattern="^(comedy|education|product|story|explainer)?$")
    provider: Optional[str] = Field(default="auto", pattern="^(auto|template|ollama)$")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Senaryo promptu boş olamaz.")
        return v.strip()

class StudioProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    scene_graph: Optional[Dict[str, Any]] = None
    total_duration_seconds: float = 0.0
    scene_count: int = 0
    character_count: int = 0
    created_at: str
    updated_at: str

class StudioProjectListResponse(BaseModel):
    items: List[StudioProjectResponse]
    total: int
    limit: int
    offset: int

class GenerateStoryResponse(BaseModel):
    scene_graph: Dict[str, Any]
    total_duration_seconds: float
    scene_count: int
    character_count: int
