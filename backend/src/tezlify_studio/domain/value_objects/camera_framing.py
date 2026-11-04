"""Format-aware camera framing profiles and the bounds-driven framing solve.

Stage 5.3 introduced this module because rendering a 1080x1920 file is not the
same thing as composing a shot for a 1080x1920 screen. The delivery format now
drives the camera: the render worker measures the real world-space extents of the
placed characters and solves a lens + distance + aim that keeps them inside the
platform's safe area, instead of reusing one landscape camera for every ratio.

Pure standard library on purpose: Blender's bundled Python has no pydantic and
imports this module from inside the headless render worker.

Geometry
--------
The worker uses ``sensor_fit = 'HORIZONTAL'``, so the horizontal field of view is
fixed by the lens and the sensor width, and the vertical field of view follows the
frame's own aspect::

    k             = (sensor_width_mm / 2) / lens_mm      # tan(half horizontal fov)
    visible_width = 2 * distance * k
    visible_height = visible_width * (height_px / width_px)

Solving for the distance that puts a subject box inside the safe band of the
target ratio is therefore a closed-form calculation, which is what
:func:`solve_camera` does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = [
    "SafeArea",
    "FramingProfile",
    "ShotIntent",
    "SubjectBounds",
    "FramingSolve",
    "PORTRAIT",
    "LANDSCAPE",
    "SQUARE",
    "profile_for_aspect",
    "profile_for_dimensions",
    "intent_for_angle",
    "solve_camera",
    "screen_box",
    "visible_extents_at_plane",
]


@dataclass(frozen=True)
class SafeArea:
    """Insets, as a fraction of the frame, that platform UI may cover.

    TikTok / Reels reserve the bottom-right controls and the caption area, and
    Shorts reserve the bottom bar; the top edge loses space to the status bar and
    the creator handle. Content that must stay readable lives inside the band
    left over after these insets.
    """

    top: float
    bottom: float
    left: float
    right: float

    @property
    def width_ratio(self) -> float:
        return max(0.1, 1.0 - self.left - self.right)

    @property
    def height_ratio(self) -> float:
        return max(0.1, 1.0 - self.top - self.bottom)

    @property
    def center_y(self) -> float:
        """Row, in 0..1 top-down frame coordinates, at the middle of the safe band."""
        return self.top + self.height_ratio / 2.0


@dataclass(frozen=True)
class FramingProfile:
    """Everything about a delivery format that the camera has to know."""

    key: str
    aspect_ratio: str
    width: int
    height: int
    safe: SafeArea
    # Share of the safe band the cast should occupy. Below 1.0 it leaves a margin
    # so an outstretched arm does not sit on the very edge of a phone screen.
    subject_fill: float
    # How far apart side-by-side characters may stand before the tall frame goes
    # to waste. Landscape keeps the authored spacing; portrait pulls the cast
    # together so the camera can push in instead of showing empty wall.
    horizontal_spacing_ratio: float
    # A tall frame shows more body than a wide one at the same distance, so the
    # shot is allowed to open up (towards the feet) instead of floating in
    # headroom. Clamped to 1.0, which already means "whole character".
    body_crop_adjust: float
    min_distance: float
    max_distance: float
    min_lens: float

    @property
    def dimension_ratio(self) -> float:
        return self.height / self.width

    @property
    def label(self) -> str:
        return f"{self.key} ({self.width}x{self.height})"


LANDSCAPE = FramingProfile(
    key="landscape",
    aspect_ratio="16:9",
    width=1920,
    height=1080,
    safe=SafeArea(top=0.05, bottom=0.10, left=0.03, right=0.03),
    subject_fill=0.94,
    horizontal_spacing_ratio=1.0,
    body_crop_adjust=1.0,
    min_distance=1.4,
    max_distance=9.0,
    min_lens=24.0,
)

PORTRAIT = FramingProfile(
    key="portrait",
    aspect_ratio="9:16",
    width=1080,
    height=1920,
    safe=SafeArea(top=0.09, bottom=0.20, left=0.04, right=0.04),
    subject_fill=0.88,
    horizontal_spacing_ratio=0.66,
    body_crop_adjust=1.14,
    min_distance=1.1,
    max_distance=9.0,
    min_lens=24.0,
)

SQUARE = FramingProfile(
    key="square",
    aspect_ratio="1:1",
    width=1080,
    height=1080,
    safe=SafeArea(top=0.07, bottom=0.16, left=0.04, right=0.04),
    subject_fill=0.92,
    horizontal_spacing_ratio=0.84,
    body_crop_adjust=1.05,
    min_distance=1.2,
    max_distance=9.0,
    min_lens=24.0,
)

_PROFILES_BY_ASPECT: Dict[str, FramingProfile] = {
    LANDSCAPE.aspect_ratio: LANDSCAPE,
    PORTRAIT.aspect_ratio: PORTRAIT,
    SQUARE.aspect_ratio: SQUARE,
}


def profile_for_aspect(aspect_ratio: Optional[str]) -> FramingProfile:
    return _PROFILES_BY_ASPECT.get(str(aspect_ratio or ""), LANDSCAPE)


def profile_for_dimensions(width: int, height: int) -> FramingProfile:
    """Fallback for legacy scenes whose aspect ratio was never recorded."""
    if height > width:
        return PORTRAIT
    if width == height:
        return SQUARE
    return LANDSCAPE


@dataclass(frozen=True)
class ShotIntent:
    """What a camera angle means in physical terms, independent of the ratio.

    ``body_crop`` is the share of the head-to-feet span kept in frame, measured
    from the top of the head down: 1.0 is a full body, 0.4 is a head-and-shoulders
    shot. ``height_offset`` keeps the slight downward tilt the studio rig uses.
    """

    base_lens: float
    height_offset: float
    body_crop: float
    key: str


_SHOT_INTENTS: Tuple[ShotIntent, ...] = (
    ShotIntent(base_lens=38.0, height_offset=0.40, body_crop=1.00, key="wide"),
    ShotIntent(base_lens=45.0, height_offset=0.20, body_crop=0.82, key="two_shot"),
    ShotIntent(base_lens=55.0, height_offset=0.10, body_crop=0.34, key="shoulder"),
    ShotIntent(base_lens=65.0, height_offset=0.00, body_crop=0.40, key="close_up"),
    ShotIntent(base_lens=48.0, height_offset=0.20, body_crop=0.72, key="medium_shot"),
)

_ANGLE_KEYWORDS: Tuple[Tuple[str, str], ...] = (
    ("wide", "wide"),
    ("establish", "wide"),
    ("two", "two_shot"),
    ("shoulder", "shoulder"),
    ("close", "close_up"),
    ("medium", "medium_shot"),
    ("mid", "medium_shot"),
)


def intent_for_angle(angle: Optional[str]) -> ShotIntent:
    text = str(angle or "").lower()
    for keyword, key in _ANGLE_KEYWORDS:
        if keyword in text:
            for intent in _SHOT_INTENTS:
                if intent.key == key:
                    return intent
    return _SHOT_INTENTS[-1]  # medium_shot


@dataclass(frozen=True)
class SubjectBounds:
    """World-space extents of the cast that must stay visible."""

    x_min: float
    x_max: float
    z_top: float
    z_bottom: float
    character_ids: Tuple[str, ...] = ()

    @property
    def width(self) -> float:
        return max(0.05, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(0.05, self.z_top - self.z_bottom)

    @property
    def center_x(self) -> float:
        return (self.x_min + self.x_max) / 2.0

    @property
    def center_z(self) -> float:
        return (self.z_top + self.z_bottom) / 2.0

    def scale_x_about(self, pivot_x: float, ratio: float) -> "SubjectBounds":
        """Pull the cast towards ``pivot_x`` for a narrower frame."""
        if ratio == 1.0:
            return self
        return SubjectBounds(
            x_min=pivot_x + (self.x_min - pivot_x) * ratio,
            x_max=pivot_x + (self.x_max - pivot_x) * ratio,
            z_top=self.z_top,
            z_bottom=self.z_bottom,
            character_ids=self.character_ids,
        )


@dataclass(frozen=True)
class FramingSolve:
    """Camera placement that answers a shot intent for one delivery format."""

    lens: float
    distance: float
    camera_x: float
    camera_y: float
    camera_z: float
    target_x: float
    target_z: float
    visible_width: float
    visible_height: float
    safe_width: float
    safe_height: float
    fits: bool
    limited_by: str
    subject: SubjectBounds
    profile_key: str
    shot_key: str

    @property
    def fill_width(self) -> float:
        return round(self.subject.width / self.safe_width, 4)

    @property
    def fill_height(self) -> float:
        return round(self.subject.height / self.safe_height, 4)

    def to_dict(self) -> dict:
        return {
            "profile": self.profile_key,
            "shot": self.shot_key,
            "lens_mm": round(self.lens, 3),
            "distance_m": round(self.distance, 4),
            "camera": [
                round(self.camera_x, 4),
                round(self.camera_y, 4),
                round(self.camera_z, 4),
            ],
            "target": [round(self.target_x, 4), 0.0, round(self.target_z, 4)],
            "visible_width_m": round(self.visible_width, 4),
            "visible_height_m": round(self.visible_height, 4),
            "subject_width_m": round(self.subject.width, 4),
            "subject_height_m": round(self.subject.height, 4),
            "fill_width": self.fill_width,
            "fill_height": self.fill_height,
            "fits_safe_area": self.fits,
            "limited_by": self.limited_by,
        }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def solve_camera(
    profile: FramingProfile,
    bounds: SubjectBounds,
    intent: ShotIntent,
    sensor_width_mm: float = 36.0,
    camera_y_base: float = 0.0,
) -> FramingSolve:
    """Place the camera so ``bounds`` fills the safe area of ``profile``.

    Distance is driven by whichever axis is tighter; when the cast cannot be
    framed from within ``max_distance`` at the shot's normal lens, the lens opens
    up instead of leaving the subjects tiny. The aim is set so the subject sits on
    the middle row of the safe band, which is what stops a portrait frame from
    turning its own headroom into dead space.
    """

    sensor_half = max(1.0, sensor_width_mm) / 2.0
    aspect = profile.height / profile.width
    safe = profile.safe
    fill = max(0.1, min(1.0, profile.subject_fill))
    target_width_ratio = safe.width_ratio * fill
    target_height_ratio = safe.height_ratio * fill

    lens = intent.base_lens
    distance = 0.0
    limited_by = "shot"
    fits = False

    # Iterate at most twice: the first pass solves distance at the shot's lens,
    # the second re-solves with a wider lens if the rig cannot physically back up
    # far enough.
    for attempt in range(2):
        k = sensor_half / lens

        need_for_width = bounds.width / (2.0 * k * target_width_ratio)
        need_for_height = bounds.height / (2.0 * k * target_height_ratio * aspect)
        required = max(need_for_width, need_for_height)
        limited_by = "width" if need_for_width >= need_for_height else "height"

        if required > profile.max_distance and attempt == 0:
            # Open the lens just enough to frame the subject from the limit.
            lens_for_max = _clamp(
                2.0 * sensor_half * target_width_ratio * profile.max_distance / bounds.width,
                profile.min_lens,
                lens,
            )
            if lens_for_max < lens:
                lens = lens_for_max
                limited_by = "lens"
                continue

        distance = _clamp(required, profile.min_distance, profile.max_distance)
        k = sensor_half / lens
        visible_width = 2.0 * distance * k
        visible_height = visible_width * aspect
        fits = (
            bounds.width <= visible_width * target_width_ratio + 1e-6
            and bounds.height <= visible_height * target_height_ratio + 1e-6
        )
        break

    k = sensor_half / lens
    visible_width = 2.0 * distance * k
    visible_height = visible_width * aspect

    target_x = bounds.center_x
    target_z = bounds.center_z + (safe.center_y - 0.5) * visible_height
    camera_z = target_z + intent.height_offset

    return FramingSolve(
        lens=lens,
        distance=distance,
        camera_x=target_x,
        camera_y=camera_y_base - distance,
        camera_z=camera_z,
        target_x=target_x,
        target_z=target_z,
        visible_width=visible_width,
        visible_height=visible_height,
        safe_width=visible_width * safe.width_ratio,
        safe_height=visible_height * safe.height_ratio,
        fits=fits,
        limited_by=limited_by,
        subject=bounds,
        profile_key=profile.key,
        shot_key=intent.key,
    )


def screen_box(profile: FramingProfile, solve: FramingSolve, bounds: SubjectBounds) -> dict:
    """Project a world box into normalised frame coordinates (0..1, top-left origin).

    Approximates the near-level camera axis, which is what the studio rig solves
    for; used by the render report to prove that heads and bodies are on screen.
    """
    x_half = solve.visible_width / 2.0
    z_half = solve.visible_height / 2.0

    def row_for_z(z: float) -> float:
        return 0.5 - (z - solve.target_z) / (2.0 * z_half)

    return {
        "x0": round((bounds.x_min - (solve.target_x - x_half)) / solve.visible_width, 4),
        "x1": round((bounds.x_max - (solve.target_x - x_half)) / solve.visible_width, 4),
        "y_top": round(row_for_z(bounds.z_top), 4),
        "y_bottom": round(row_for_z(bounds.z_bottom), 4),
    }


def visible_extents_at_plane(
    profile: FramingProfile,
    solve: FramingSolve,
    plane_y: float,
    sensor_width_mm: float = 36.0,
) -> Tuple[float, float, float, float]:
    """World x/z window the camera can see on a plane at ``plane_y``.

    The backdrop has to cover this rectangle or the extra headroom of a portrait
    frame turns into the black world background.
    """
    sensor_half = max(1.0, sensor_width_mm) / 2.0
    k = sensor_half / solve.lens
    distance = max(0.05, plane_y - solve.camera_y)
    half_width = distance * k
    half_height = half_width * (profile.height / profile.width)
    centre_z = solve.target_z
    return (
        solve.target_x - half_width,
        solve.target_x + half_width,
        centre_z - half_height,
        centre_z + half_height,
    )
