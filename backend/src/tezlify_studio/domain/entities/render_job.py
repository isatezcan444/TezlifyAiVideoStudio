from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from tezlify_studio.domain.enums.studio_status import RenderJobStatus
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata

@dataclass
class RenderJob:
    id: str
    project_id: str
    status: RenderJobStatus = RenderJobStatus.PENDING
    progress_percent: float = 0.0
    current_step: str = "Pending"
    output_video_path: Optional[str] = None
    output_metadata: Optional[RenderOutputMetadata] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def start(self, step: str = "Starting render") -> None:
        self.status = RenderJobStatus.RUNNING
        self.current_step = step
        self.started_at = datetime.now(timezone.utc)
        self.progress_percent = 5.0

    def update_progress(self, percent: float, step: str) -> None:
        self.progress_percent = max(0.0, min(100.0, percent))
        self.current_step = step

    def complete(self, video_path: str, metadata: RenderOutputMetadata) -> None:
        self.status = RenderJobStatus.COMPLETED
        self.progress_percent = 100.0
        self.current_step = "Render completed successfully"
        self.output_video_path = video_path
        self.output_metadata = metadata
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        self.status = RenderJobStatus.FAILED
        self.error_message = error
        self.current_step = f"Failed: {error}"
        self.completed_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        self.status = RenderJobStatus.CANCELLED
        self.current_step = "Cancelled"
        self.completed_at = datetime.now(timezone.utc)
