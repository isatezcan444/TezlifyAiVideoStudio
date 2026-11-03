import os
import json
import shutil
import subprocess
import struct
from typing import Optional
from tezlify_studio.application.ports.video_probe_port import VideoProbePort
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata

class VideoProbeImpl(VideoProbePort):
    def __init__(self, ffmpeg_bin: Optional[str] = None, ffprobe_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg")
        self.ffprobe_bin = ffprobe_bin or shutil.which("ffprobe")

    def is_ffmpeg_available(self) -> bool:
        return bool(self.ffmpeg_bin and os.path.exists(self.ffmpeg_bin))

    def is_ffprobe_available(self) -> bool:
        return bool(self.ffprobe_bin and os.path.exists(self.ffprobe_bin))

    def probe_video(self, file_path: str) -> VideoMetadata:
        if self.is_ffprobe_available():
            try:
                return self._probe_with_ffprobe(file_path)
            except Exception:
                # Fallback to python inspection if ffprobe failed on this specific file
                pass

        return self._probe_with_python_fallback(file_path)

    def _probe_with_ffprobe(self, file_path: str) -> VideoMetadata:
        cmd = [
            self.ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe returned code {result.returncode}")

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        duration = None
        if "duration" in fmt:
            try:
                duration = round(float(fmt["duration"]), 2)
            except (ValueError, TypeError):
                pass
        elif video_stream and "duration" in video_stream:
            try:
                duration = round(float(video_stream["duration"]), 2)
            except (ValueError, TypeError):
                pass

        width = None
        height = None
        fps = None
        aspect_ratio = None
        video_codec = None

        if video_stream:
            width = video_stream.get("width")
            height = video_stream.get("height")
            video_codec = video_stream.get("codec_name")

            # Parse framerate (e.g., "30/1", "24000/1001")
            r_frame_rate = video_stream.get("r_frame_rate", "")
            if "/" in r_frame_rate:
                try:
                    num, den = map(float, r_frame_rate.split("/"))
                    if den > 0:
                        fps = round(num / den, 2)
                except (ValueError, ZeroDivisionError):
                    pass

            if width and height and height > 0:
                aspect_ratio = f"{round(width / height, 2)}:1"

        audio_codec = audio_stream.get("codec_name") if audio_stream else None

        return VideoMetadata(
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            video_codec=video_codec,
            audio_codec=audio_codec,
            aspect_ratio=aspect_ratio,
            probe_source="ffprobe",
        )

    def _probe_with_python_fallback(self, file_path: str) -> VideoMetadata:
        """
        Pure-Python fallback when ffprobe is not installed.
        Inspects ISO BMFF (MP4/MOV) boxes (mvhd / tkhd) if possible.
        """
        duration = None
        width = None
        height = None
        aspect_ratio = None

        try:
            with open(file_path, "rb") as f:
                # Basic search for mvhd box in the first 2MB or whole file
                data = f.read(2 * 1024 * 1024)
                mvhd_idx = data.find(b"mvhd")
                if mvhd_idx != -1 and mvhd_idx + 24 < len(data):
                    version = data[mvhd_idx + 4]
                    if version == 0:
                        # 32-bit timescale and duration
                        timescale, raw_duration = struct.unpack(">II", data[mvhd_idx + 16 : mvhd_idx + 24])
                        if timescale > 0:
                            duration = round(raw_duration / timescale, 2)
                    elif version == 1 and mvhd_idx + 36 < len(data):
                        # 64-bit timescale and duration
                        timescale, raw_duration = struct.unpack(">IQ", data[mvhd_idx + 24 : mvhd_idx + 36])
                        if timescale > 0:
                            duration = round(raw_duration / timescale, 2)

                # Search for tkhd box to extract track dimensions
                tkhd_idx = data.find(b"tkhd")
                if tkhd_idx != -1 and tkhd_idx + 84 < len(data):
                    w_fixed = struct.unpack(">I", data[tkhd_idx + 76 : tkhd_idx + 80])[0]
                    h_fixed = struct.unpack(">I", data[tkhd_idx + 80 : tkhd_idx + 84])[0]
                    width_val = w_fixed >> 16
                    height_val = h_fixed >> 16
                    if width_val > 0 and height_val > 0:
                        width = width_val
                        height = height_val
                        aspect_ratio = f"{round(width / height, 2)}:1"
        except Exception:
            pass

        return VideoMetadata(
            duration_seconds=duration,
            width=width,
            height=height,
            fps=30.0 if duration else None,
            video_codec="h264 (inferred)" if file_path.endswith((".mp4", ".m4v")) else None,
            audio_codec="aac (inferred)" if file_path.endswith((".mp4", ".m4v")) else None,
            aspect_ratio=aspect_ratio,
            probe_source="python_fallback",
        )

    def generate_thumbnail(self, video_path: str, output_path: str, at_second: float = 1.0) -> Optional[str]:
        if not self.is_ffmpeg_available():
            return None

        try:
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-ss", str(at_second),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "3",
                output_path,
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if res.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass

        return None
