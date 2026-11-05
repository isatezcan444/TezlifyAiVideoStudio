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
    has_audio: bool = True
    audio_codec: str = "aac"
    # Stage 5.5: measured loudness, not a stream header. `has_audio` was true for
    # files whose audio track was digital silence, because the engines synthesise
    # a silent AAC track when there is nothing to mix. Defaults keep already
    # stored renders readable.
    audio_audible: bool = True
    audio_mean_db: Optional[float] = None
    audio_max_db: Optional[float] = None
    audio_reason: str = ""
    frame_count: int = Field(default=0, ge=0)
    render_duration_seconds: float = Field(default=0.0, ge=0.0)
    engine: str = "BLENDER_EEVEE"

    # Stage 4.5 composition details (optional for backwards compatibility)
    composition_id: Optional[str] = None
    composition_name: Optional[str] = None
    format: Optional[str] = None
    subtitle_file_path: Optional[str] = None
    subtitle_cue_count: int = 0
    text_layer_count: int = 0
    transition_count: int = 0
    scene_count: int = 0

    # Stage 5.4 lip sync (optional for backwards compatibility with stored renders)
    lip_sync: Optional[dict] = None
    # Stage 5.5 animation plan actually used by this render
    animation: Optional[dict] = None
