from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class VideoMetadataDTO:
    duration_seconds: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    video_codec: Optional[str]
    audio_codec: Optional[str]
    aspect_ratio: Optional[str]
    probe_source: str
    resolution_label: str

@dataclass
class MediaAssetDTO:
    id: str
    filename: str
    original_filename: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    status: str
    thumbnail_path: Optional[str]
    created_at: str
    updated_at: str
    metadata: Optional[VideoMetadataDTO]

@dataclass
class MediaListResponseDTO:
    items: List[MediaAssetDTO]
    total: int

@dataclass
class ImportVideoRequestDTO:
    original_filename: str
    mime_type: str
    file_stream: any

@dataclass
class SystemStatusDTO:
    status: str
    app_name: str
    version: str
    os_name: str
    python_version: str
    ffmpeg_installed: bool
    ffprobe_installed: bool
    blender_installed: bool
    data_dir: str
    disk_total_gb: float
    disk_free_gb: float
    total_videos: int
    total_storage_bytes: int

