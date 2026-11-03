from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    aspect_ratio: Optional[str] = None
    probe_source: str = "ffprobe"

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "Bilinmiyor"

