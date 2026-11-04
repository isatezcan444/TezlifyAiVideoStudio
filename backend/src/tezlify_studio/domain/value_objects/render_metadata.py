from typing import Optional
from pydantic import BaseModel, Field

class RenderOutputMetadata(BaseModel):
    video_file_path: str
    file_size_bytes: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: int = Field(default=30, gt=0)
    video_codec: str = "h264"
    pixel_format: str = "yuv420p"
    container: str = "mp4"
    frame_count: int = Field(default=0, ge=0)
    render_duration_seconds: float = Field(default=0.0, ge=0.0)
    engine: str = "BLENDER_WORKBENCH"
