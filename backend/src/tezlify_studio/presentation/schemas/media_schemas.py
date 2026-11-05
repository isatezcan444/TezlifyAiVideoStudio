from pydantic import BaseModel, Field
from typing import Optional, List

class VideoMetadataSchema(BaseModel):
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    aspect_ratio: Optional[str] = None
    probe_source: str
    resolution_label: str

class MediaAssetResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    status: str
    thumbnail_path: Optional[str] = None
    created_at: str
    updated_at: str
    metadata: Optional[VideoMetadataSchema] = None

class MediaListResponse(BaseModel):
    items: List[MediaAssetResponse]
    total: int

class SystemStatusResponse(BaseModel):
    status: str
    app_name: str
    version: str
    os_name: str
    python_version: str
    ffmpeg_installed: bool
    ffprobe_installed: bool
    data_dir: str
    disk_total_gb: float
    disk_free_gb: float
    total_videos: int
    total_storage_bytes: int

class ErrorResponse(BaseModel):
    detail: str
    error_code: str

