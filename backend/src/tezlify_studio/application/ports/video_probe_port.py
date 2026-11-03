from abc import ABC, abstractmethod
from typing import Optional
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata

class VideoProbePort(ABC):
    @abstractmethod
    def probe_video(self, file_path: str) -> VideoMetadata:
        """
        Inspects video file and returns extracted technical metadata.
        Falls back to pure-Python metadata extraction if external tools are unavailable.
        """
        pass

    @abstractmethod
    def generate_thumbnail(self, video_path: str, output_path: str, at_second: float = 1.0) -> Optional[str]:
        """
        Generates thumbnail image from video frame. Returns thumbnail path if successful.
        """
        pass

    @abstractmethod
    def is_ffprobe_available(self) -> bool:
        pass

    @abstractmethod
    def is_ffmpeg_available(self) -> bool:
        pass
