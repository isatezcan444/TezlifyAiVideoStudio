"""Video composition domain model (Stage 4.5).

A :class:`VideoComposition` describes how already rendered animation scenes are
assembled into a final, publishable video: scene order, transitions, text
overlays, subtitles, audio mix and delivery format.

The model is deliberately independent from the Blender renderer. The renderer
turns each scene into a video clip; this model only describes the edit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidCompositionException,
)

HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class VideoFormat(str, Enum):
    """Supported delivery formats for the first composition release."""

    LANDSCAPE_16_9 = "16:9"
    PORTRAIT_9_16 = "9:16"
    SQUARE_1_1 = "1:1"


FORMAT_DIMENSIONS: Dict[VideoFormat, tuple[int, int]] = {
    VideoFormat.LANDSCAPE_16_9: (1920, 1080),
    VideoFormat.PORTRAIT_9_16: (1080, 1920),
    VideoFormat.SQUARE_1_1: (1080, 1080),
}

ALLOWED_COMPOSITION_FPS = {24, 25, 30, 60}


class CompositionTransition(str, Enum):
    CUT = "cut"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CROSSFADE = "crossfade"


class TextAnchor(str, Enum):
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class CompositionScene(BaseModel):
    """One scene in the edit. ``transition`` describes the exit to the next scene."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(..., min_length=1)
    transition: CompositionTransition = Field(default=CompositionTransition.CUT)
    transition_duration_seconds: float = Field(default=0.0, ge=0.0, le=5.0)

    @model_validator(mode="after")
    def validate_transition(self) -> "CompositionScene":
        if self.transition == CompositionTransition.CROSSFADE and self.transition_duration_seconds <= 0:
            raise InvalidCompositionException(
                "Crossfade geçişi için geçiş süresi 0'dan büyük olmalıdır."
            )
        if self.transition in (CompositionTransition.FADE_IN, CompositionTransition.FADE_OUT):
            if self.transition_duration_seconds <= 0:
                raise InvalidCompositionException(
                    f"{self.transition.value} geçişi için geçiş süresi 0'dan büyük olmalıdır."
                )
        return self


class TextLayer(BaseModel):
    """A timed, positioned text overlay rendered onto the final video."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=500)
    start_time: float = Field(default=0.0, ge=0.0)
    end_time: float = Field(..., gt=0.0)
    anchor: TextAnchor = Field(default=TextAnchor.BOTTOM_CENTER)
    x_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    y_ratio: float = Field(default=0.82, ge=0.0, le=1.0)
    font_size: int = Field(default=64, ge=8, le=300)
    color: str = Field(default="#FFFFFF", pattern=HEX_COLOR_PATTERN)
    background_color: Optional[str] = Field(default="#000000", pattern=HEX_COLOR_PATTERN)
    background_opacity: float = Field(default=0.55, ge=0.0, le=1.0)
    fade_in_seconds: float = Field(default=0.3, ge=0.0, le=5.0)
    fade_out_seconds: float = Field(default=0.3, ge=0.0, le=5.0)
    max_width_ratio: float = Field(default=0.82, ge=0.1, le=1.0)
    bold: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_text_timing(self) -> "TextLayer":
        if self.end_time <= self.start_time:
            raise InvalidCompositionException(
                f"Metin katmanı '{self.id}' için bitiş zamanı başlangıçtan büyük olmalıdır."
            )
        display = self.end_time - self.start_time
        if self.fade_in_seconds + self.fade_out_seconds > display:
            raise InvalidCompositionException(
                f"Metin katmanı '{self.id}' fade süreleri görünme süresinden uzun olamaz."
            )
        return self


class SubtitleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(default=True)
    burn_in: bool = Field(default=True)
    save_srt: bool = Field(default=True)
    font_size: int = Field(default=46, ge=12, le=160)
    color: str = Field(default="#FFFFFF", pattern=HEX_COLOR_PATTERN)
    background_color: str = Field(default="#000000", pattern=HEX_COLOR_PATTERN)
    background_opacity: float = Field(default=0.62, ge=0.0, le=1.0)
    margin_bottom_ratio: float = Field(default=0.075, ge=0.0, le=0.4)
    max_width_ratio: float = Field(default=0.84, ge=0.2, le=1.0)
    max_chars_per_line: int = Field(default=44, ge=12, le=120)


class AudioMixSettings(BaseModel):
    """Dialogue/music mixing controls. Music is optional and never auto-generated."""

    model_config = ConfigDict(extra="forbid")

    dialogue_volume_db: float = Field(default=0.0, ge=-40.0, le=12.0)
    music_file: Optional[str] = Field(default=None)
    music_volume_db: float = Field(default=-20.0, ge=-60.0, le=6.0)
    limiter_enabled: bool = Field(default=True)
    limiter_limit: float = Field(default=0.95, gt=0.0, le=1.0)


class VideoComposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    name: str = Field(default="Ana Kompozisyon", min_length=1, max_length=200)
    format: VideoFormat = Field(default=VideoFormat.LANDSCAPE_16_9)
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: int = Field(default=30)
    scenes: List[CompositionScene] = Field(..., min_length=1)
    text_layers: List[TextLayer] = Field(default_factory=list)
    subtitles: SubtitleSettings = Field(default_factory=SubtitleSettings)
    audio: AudioMixSettings = Field(default_factory=AudioMixSettings)
    output_format: str = Field(default="mp4", pattern="^mp4$")

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "VideoComposition":
        expected_w, expected_h = FORMAT_DIMENSIONS[self.format]
        # The delivery format is authoritative. This keeps API/UI callers from
        # producing a 9:16 file whose width/height silently stayed 1920x1080.
        self.width = expected_w
        self.height = expected_h

        if self.fps not in ALLOWED_COMPOSITION_FPS:
            raise InvalidCompositionException(
                f"Desteklenmeyen FPS: {self.fps}. İzin verilen değerler: {sorted(ALLOWED_COMPOSITION_FPS)}"
            )

        seen = set()
        for item in self.scenes:
            if item.scene_id in seen:
                raise InvalidCompositionException(
                    f"Sahne '{item.scene_id}' kompozisyonda birden fazla kez yer alamaz."
                )
            seen.add(item.scene_id)

        seen_text_ids = set()
        for layer in self.text_layers:
            if layer.id in seen_text_ids:
                raise InvalidCompositionException(
                    f"Metin katmanı ID '{layer.id}' birden fazla kez kullanılamaz."
                )
            seen_text_ids.add(layer.id)
        return self

    @property
    def aspect_ratio(self) -> str:
        return self.format.value


@dataclass(frozen=True)
class CompositionTimelineEntry:
    scene_id: str
    order: int
    duration_seconds: float
    start_time: float
    end_time: float
    transition: CompositionTransition
    transition_duration_seconds: float

    @property
    def overlaps_next(self) -> bool:
        return self.transition == CompositionTransition.CROSSFADE


@dataclass(frozen=True)
class CompositionTimeline:
    entries: List[CompositionTimelineEntry]
    total_duration_seconds: float

    def entry_for(self, scene_id: str) -> CompositionTimelineEntry:
        for entry in self.entries:
            if entry.scene_id == scene_id:
                return entry
        raise KeyError(scene_id)

    @property
    def total_overlap_seconds(self) -> float:
        return sum(
            e.transition_duration_seconds
            for e in self.entries
            if e.overlaps_next
        )


def build_composition_timeline(
    composition: VideoComposition,
    scene_durations: Dict[str, float],
) -> CompositionTimeline:
    """Computes absolute scene start/end times.

    Crossfade scenes overlap, so the total duration is
    ``sum(scene durations) - sum(crossfade durations)``. Cut/fade-in/fade-out
    transitions are sequential and do not shorten the timeline.
    """

    if not composition.scenes:
        raise InvalidCompositionException("Kompozisyon en az bir sahne içermelidir.")

    missing = [s.scene_id for s in composition.scenes if s.scene_id not in scene_durations]
    if missing:
        raise InvalidCompositionException(
            "Kompozisyondaki sahne SceneGraph içinde bulunamadı: " + ", ".join(missing)
        )

    entries: List[CompositionTimelineEntry] = []
    cursor = 0.0

    for index, scene in enumerate(composition.scenes):
        duration = float(scene_durations[scene.scene_id])
        if duration <= 0:
            raise InvalidCompositionException(
                f"Sahne '{scene.scene_id}' süresi 0'dan büyük olmalıdır."
            )

        is_last = index == len(composition.scenes) - 1
        if is_last:
            # A closing scene may still fade in/out. Crossfade needs a next
            # scene, so a dangling crossfade is treated as a cut.
            if scene.transition in (
                CompositionTransition.FADE_IN,
                CompositionTransition.FADE_OUT,
            ):
                transition = scene.transition
                transition_duration = scene.transition_duration_seconds
            else:
                transition = CompositionTransition.CUT
                transition_duration = 0.0
        else:
            transition = scene.transition
            transition_duration = scene.transition_duration_seconds

        if transition == CompositionTransition.CROSSFADE:
            if transition_duration >= duration:
                raise InvalidCompositionException(
                    f"Sahne '{scene.scene_id}' crossfade süresi ({transition_duration}s) "
                    f"sahne süresinden ({duration}s) kısa olmalıdır."
                )
            next_scene = composition.scenes[index + 1]
            next_duration = float(scene_durations[next_scene.scene_id])
            if transition_duration >= next_duration:
                raise InvalidCompositionException(
                    f"Sahne '{next_scene.scene_id}' crossfade süresi ({transition_duration}s) "
                    f"sonraki sahne süresinden ({next_duration}s) kısa olmalıdır."
                )

        if transition in (CompositionTransition.FADE_IN, CompositionTransition.FADE_OUT):
            if transition_duration > duration:
                raise InvalidCompositionException(
                    f"Sahne '{scene.scene_id}' fade süresi ({transition_duration}s) "
                    f"sahne süresinden ({duration}s) uzun olamaz."
                )

        start = round(cursor, 6)
        end = round(start + duration, 6)
        entries.append(
            CompositionTimelineEntry(
                scene_id=scene.scene_id,
                order=index + 1,
                duration_seconds=duration,
                start_time=start,
                end_time=end,
                transition=transition,
                transition_duration_seconds=transition_duration,
            )
        )

        if transition == CompositionTransition.CROSSFADE:
            cursor = end - transition_duration
        else:
            cursor = end

    total = round(entries[-1].end_time, 6)
    return CompositionTimeline(entries=entries, total_duration_seconds=max(0.0, total))


def validate_composition_against_scene_ids(
    composition: VideoComposition,
    scene_ids: List[str],
) -> None:
    """Requires every SceneGraph scene to appear exactly once in the edit."""

    expected = set(scene_ids)
    actual = {s.scene_id for s in composition.scenes}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        parts = []
        if missing:
            parts.append("eksik sahneler: " + ", ".join(missing))
        if extra:
            parts.append("bilinmeyen sahneler: " + ", ".join(extra))
        raise InvalidCompositionException(
            "Kompozisyon sahne listesi SceneGraph ile eşleşmiyor (" + "; ".join(parts) + ")."
        )
