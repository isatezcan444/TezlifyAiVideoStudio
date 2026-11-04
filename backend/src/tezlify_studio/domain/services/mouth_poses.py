"""Viseme mouth poses (Stage 5.4).

Pure standard library on purpose, for the same reason as ``camera_framing``:
Blender's bundled Python has no pydantic and imports this module directly from
the headless render worker. Keeping the pose table dependency-free means the
renderer and the backend tests read exactly the same numbers.

The channels were chosen by measurement, not by assumption. On the built rig the
mouth cylinder is rotated 90 degrees about X, so its local Z maps to world depth
and spans only 8 mm — animating it changed 0.19% of the pixels in a tight head
shot, which is why the pre-5.4 open/close flap is nearly invisible on screen.
Width (local X), opening (local Y -> world Z) and a jaw offset are what a viewer
can actually see.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from tezlify_studio.domain.enums.studio_status import MouthViseme


@dataclass(frozen=True)
class MouthPose:
    """A pose expressed against the character's own rest transform.

    Multipliers rather than absolutes, because the built mouth differs per gender
    and expression (cheerful is wider than neutral) and each character must keep
    its own look.
    """

    width_scale: float   # multiplier on rest scale.x
    open_scale: float    # multiplier on rest scale.y
    jaw_offset: float    # metres added to rest location.z (negative = opens down)


MOUTH_POSES: Dict[MouthViseme, MouthPose] = {
    MouthViseme.REST:         MouthPose(1.00, 1.00, 0.000),
    MouthViseme.CLOSED:       MouthPose(0.95, 0.62, -0.002),
    MouthViseme.FV:           MouthPose(0.90, 0.80, 0.008),
    MouthViseme.DENTAL:       MouthPose(1.06, 1.12, -0.012),
    MouthViseme.SIBILANT:     MouthPose(1.20, 0.86, -0.004),
    MouthViseme.VELAR:        MouthPose(0.95, 1.25, -0.016),
    MouthViseme.OPEN:         MouthPose(1.00, 1.90, -0.034),
    MouthViseme.WIDE:         MouthPose(1.38, 1.12, -0.006),
    MouthViseme.ROUND:        MouthPose(0.78, 1.48, -0.022),
    MouthViseme.NARROW_ROUND: MouthPose(0.68, 1.22, -0.018),
}

#: Hard limits that keep any pose inside the face. The widest pose (WIDE at 1.38)
#: and the deepest jaw (OPEN at -34 mm) both sit inside these with room to spare.
POSE_LIMITS: Dict[str, Tuple[float, float]] = {
    "width_scale": (0.50, 1.60),
    "open_scale": (0.40, 2.20),
    "jaw_offset": (-0.050, 0.020),
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def pose_for(viseme) -> MouthPose:
    """Clamped pose for a viseme; anything unknown falls back to rest.

    Accepts a ``MouthViseme`` or its string value, because the render worker
    receives plain strings through the JSON manifest.
    """
    if isinstance(viseme, str):
        try:
            viseme = MouthViseme(viseme)
        except ValueError:
            viseme = MouthViseme.REST
    pose = MOUTH_POSES.get(viseme, MOUTH_POSES[MouthViseme.REST])
    return MouthPose(
        width_scale=_clamp(pose.width_scale, *POSE_LIMITS["width_scale"]),
        open_scale=_clamp(pose.open_scale, *POSE_LIMITS["open_scale"]),
        jaw_offset=_clamp(pose.jaw_offset, *POSE_LIMITS["jaw_offset"]),
    )
