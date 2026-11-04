"""Shared measurement helpers for the Stage 5.3 vertical-composition evidence.

Every number in STAGE_5_3_VERTICAL_COMPOSITION_REPORT.md comes from these
functions so that "no black padding" and "faces are visible" are measurable
claims rather than impressions. Pillow only — no extra test dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
from PIL import Image

# A pixel counts as "black" when its brightest channel is below this value.
BLACK_THRESHOLD = 14


class Frame:
    def __init__(self, path: str):
        self.path = path
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            self.width, self.height = rgb.size
            self._data = rgb.tobytes()
        self._stride = self.width * 3

    def _row_max(self, y: int) -> int:
        offset = y * self._stride
        return max(self._data[offset:offset + self._stride])

    def _col_max(self, x: int) -> int:
        offset = x * 3
        # R, G and B of every row share the same stride, so slice each channel
        # and take the largest value seen in the column.
        return max(
            max(self._data[offset::self._stride]),
            max(self._data[offset + 1::self._stride]),
            max(self._data[offset + 2::self._stride]),
        )

    def row_is_black(self, y: int) -> bool:
        return self._row_max(y) < BLACK_THRESHOLD

    def col_is_black(self, x: int) -> bool:
        return self._col_max(x) < BLACK_THRESHOLD

    def black_edge_ratio(self) -> dict:
        """Fraction of the frame covered by a fully black band on each edge.

        A letterbox/padding band is a run of rows (or columns) that are *entirely*
        black and touch the edge. Dim scenery does not count as padding.
        """
        def run(start: int, stop: int, step: int, is_black) -> int:
            count = 0
            index = start
            while (step > 0 and index < stop) or (step < 0 and index > stop):
                if is_black(index):
                    count += 1
                    index += step
                else:
                    break
            return count

        top = run(0, self.height, 1, self.row_is_black)
        bottom = run(self.height - 1, -1, -1, self.row_is_black)
        left = run(0, self.width, 1, self.col_is_black)
        right = run(self.width - 1, -1, -1, self.col_is_black)

        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "top_black_band_px": top,
            "bottom_black_band_px": bottom,
            "left_black_band_px": left,
            "right_black_band_px": right,
            "top_black_band_ratio": round(top / self.height, 4),
            "bottom_black_band_ratio": round(bottom / self.height, 4),
            "left_black_band_ratio": round(left / self.width, 4),
            "right_black_band_ratio": round(right / self.width, 4),
            "max_edge_black_band_ratio": round(
                max(top / self.height, bottom / self.height,
                    left / self.width, right / self.width), 4
            ),
        }

    def black_pixel_ratio(self, sample_step: int = 4) -> float:
        """Share of near-black pixels, estimated on a regular subsample."""
        total = 0
        black = 0
        for y in range(0, self.height, sample_step):
            offset = y * self._stride
            row = self._data[offset:offset + self._stride]
            for x in range(0, len(row), 3 * sample_step):
                total += 1
                if max(row[x], row[x + 1], row[x + 2]) < BLACK_THRESHOLD:
                    black += 1
        return round(black / max(1, total), 4)

    def content_box(self) -> dict:
        """Outermost rows/cols that contain any non-black pixel."""
        top = 0
        while top < self.height - 1 and self.row_is_black(top):
            top += 1
        bottom = self.height - 1
        while bottom > top and self.row_is_black(bottom):
            bottom -= 1
        left = 0
        while left < self.width - 1 and self.col_is_black(left):
            left += 1
        right = self.width - 1
        while right > left and self.col_is_black(right):
            right -= 1
        return {
            "top": top, "bottom": bottom, "left": left, "right": right,
            "coverage_ratio": round(
                ((bottom - top + 1) / self.height) * ((right - left + 1) / self.width), 4
            ),
        }


def measure_frame(path: str) -> dict:
    frame = Frame(path)
    result = frame.black_edge_ratio()
    result["global_black_pixel_ratio"] = frame.black_pixel_ratio()
    result["content_box"] = frame.content_box()
    return result


def extract_frames(video_path: str, timestamps: list[float], out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    produced = []
    for ts in timestamps:
        target = os.path.join(out_dir, f"t{ts:05.2f}s.png")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ts}", "-i", video_path, "-frames:v", "1", target],
            check=True,
            capture_output=True,
        )
        produced.append(target)
    return produced


def ffprobe_streams(video_path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def ffprobe_summary(video_path: str) -> dict:
    probe = ffprobe_streams(video_path)
    video = next((s for s in probe["streams"] if s.get("codec_type") == "video"), {})
    audio = next((s for s in probe["streams"] if s.get("codec_type") == "audio"), {})
    fmt = probe.get("format", {})
    return {
        "file": video_path,
        "width": video.get("width"),
        "height": video.get("height"),
        "display_aspect_ratio": video.get("display_aspect_ratio"),
        "sample_aspect_ratio": video.get("sample_aspect_ratio"),
        "codec_name": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "avg_frame_rate": video.get("avg_frame_rate"),
        "duration": round(float(fmt.get("duration", 0.0)), 3),
        "size_bytes": int(fmt.get("size", 0)),
        "has_video_stream": bool(video),
        "has_audio_stream": bool(audio),
        "audio_codec": audio.get("codec_name"),
        "audio_sample_rate": audio.get("sample_rate"),
        "audio_channels": audio.get("channels"),
    }


def write_json(path: str, payload) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
