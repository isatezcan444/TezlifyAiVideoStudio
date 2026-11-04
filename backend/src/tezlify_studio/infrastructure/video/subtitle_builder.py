"""SRT subtitle generation from SceneDialogue data."""

from __future__ import annotations

import os
import subprocess
import textwrap
from dataclasses import dataclass
from typing import List

from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.domain.value_objects.video_composition import (
    CompositionTimeline,
    SubtitleSettings,
    VideoComposition,
)


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str
    scene_id: str
    character_id: str


def probe_media_duration(file_path: str) -> float:
    """Returns media duration in seconds, or 0.0 when unavailable."""

    if not file_path or not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        return 0.0

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return max(0.0, round(float(result.stdout.strip()), 3))
    except Exception:
        pass
    return 0.0


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrap_subtitle(text: str, max_chars: int) -> str:
    clean = " ".join(text.split())
    if max_chars <= 0:
        return clean
    return "\n".join(textwrap.wrap(clean, width=max_chars, break_long_words=False, break_on_hyphens=False))


def build_subtitle_cues(
    scene_graph: SceneGraph,
    composition: VideoComposition,
    timeline: CompositionTimeline,
    subtitle_settings: SubtitleSettings,
) -> List[SubtitleCue]:
    """Builds cues using measured audio durations when audio is available.

    The subtitle end time follows the real spoken audio duration, not the
    approximate animation length. If the audio is longer than the scene, the
    cue is clamped to the composition duration rather than silently truncated.
    """

    scene_by_id = {scene.scene_id: scene for scene in scene_graph.scenes}
    total_duration = timeline.total_duration_seconds
    cues: List[SubtitleCue] = []
    index = 1

    for composition_scene in composition.scenes:
        scene = scene_by_id.get(composition_scene.scene_id)
        if not scene:
            continue
        entry = timeline.entry_for(scene.scene_id)

        for dialogue in sorted(scene.dialogues, key=lambda d: d.start_time):
            measured = probe_media_duration(dialogue.audio_file or "")
            spoken = measured if measured > 0 else max(0.0, dialogue.end_time - dialogue.start_time)
            if spoken <= 0:
                continue

            start = round(entry.start_time + dialogue.start_time, 3)
            end = round(start + spoken, 3)

            if start >= total_duration:
                continue
            end = min(end, total_duration)
            if end - start < 0.25:
                end = min(total_duration, start + 0.25)

            wrapped = _wrap_subtitle(dialogue.text, subtitle_settings.max_chars_per_line)
            if not wrapped.strip():
                continue

            cues.append(
                SubtitleCue(
                    index=index,
                    start_seconds=start,
                    end_seconds=end,
                    text=wrapped,
                    scene_id=scene.scene_id,
                    character_id=dialogue.character_id,
                )
            )
            index += 1

    return cues


def write_srt(cues: List[SubtitleCue], output_path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    lines: List[str] = []
    for cue in cues:
        lines.append(str(cue.index))
        lines.append(
            f"{_format_srt_timestamp(cue.start_seconds)} --> {_format_srt_timestamp(cue.end_seconds)}"
        )
        lines.append(cue.text)
        lines.append("")

    with open(output_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
    return output_path
