from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata

@dataclass
class MediaAsset:
    id: str
    filename: str
    original_filename: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    status: MediaStatus = MediaStatus.PENDING
    thumbnail_path: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[VideoMetadata] = None

    def mark_ready(self, metadata: Optional[VideoMetadata] = None, thumbnail_path: Optional[str] = None) -> None:
        self.status = MediaStatus.READY
        if metadata:
            self.metadata = metadata
        if thumbnail_path:
            self.thumbnail_path = thumbnail_path
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self) -> None:
        self.status = MediaStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)

