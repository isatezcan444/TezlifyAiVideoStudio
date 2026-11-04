from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class StudioProjectDTO:
    id: str
    title: str
    description: str
    status: str
    scene_graph: Optional[Dict[str, Any]]
    total_duration_seconds: float
    scene_count: int
    character_count: int
    created_at: str
    updated_at: str

@dataclass
class CreateStudioProjectRequestDTO:
    title: str
    description: str = ""
    scene_graph: Optional[Dict[str, Any]] = None

@dataclass
class UpdateStudioProjectRequestDTO:
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    scene_graph: Optional[Dict[str, Any]] = None

@dataclass
class GenerateStoryRequestDTO:
    prompt: str
    target_duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = "16:9"
    genre: Optional[str] = None
    provider: Optional[str] = "auto"  # "auto", "template", "ollama"
