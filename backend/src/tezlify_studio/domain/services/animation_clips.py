"""Reusable animation clips for the Blender characters.

Stdlib-only on purpose: Blender's Python has no pydantic, so this module and
`animation_plan.py` are imported directly by `render_worker.py`. That is the same
boundary `camera_framing.py` and `mouth_poses.py` already respect.

A clip is a list of `(time, pose)` keys where `time` is normalised over the clip's
own duration and `pose` maps a control target to channel deltas. Sampling eases
between consecutive keys, so every clip has an explicit start pose, a main
movement and a return - which is what the brief asks for instead of a single sine
function.

Channel conventions, all relative to the character's own rest transform:
  "rot"   euler radians, object-local XYZ
  "loc"   metres, object-local XYZ
  "scale" multiplier per axis (1.0 = unchanged)
Targets are the control names resolved by the worker from the rig hierarchy:
  root, torso, head, arm_l, arm_r, elbow_l, elbow_r, wrist_l, wrist_r,
  brow_l, brow_r, eye_l, eye_r, pupil_l, pupil_r, mouth
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

Pose = Dict[str, Dict[str, Tuple[float, ...]]]
Keys = Sequence[Tuple[float, Pose]]

_HEAD_TARGETS = frozenset({"head", "brow_l", "brow_r", "eye_l", "eye_r",
                           "pupil_l", "pupil_r"})
_ARM_TARGETS = frozenset({"arm_l", "arm_r", "elbow_l", "elbow_r", "wrist_l", "wrist_r"})
_BODY_TARGETS = frozenset({"root", "torso"})

_ATTENTION = ("head",)
_GESTURE = ("arms",)
_WHOLE_BODY = ("body", "arms", "head")

# Declared ownership for the clips where the channels they touch would mislead:
# a greeting's small head tilt is decoration, not a gaze cue.
_RESOURCE_OVERRIDES = {
    "look_at_partner": _ATTENTION,
    "turn_toward_partner": _ATTENTION,
    "greeting": _GESTURE,
    "waving": _GESTURE,
    "pointing": _GESTURE,
    "explain_with_hands": _GESTURE,
    "ask_question": _GESTURE,
    "shrugging": _GESTURE,
    "hand_gesture": _GESTURE,
    "surprised": _WHOLE_BODY,
    "react_to_partner": _WHOLE_BODY,
}


def ease(u: float) -> float:
    """Smoothstep. Keeps pose-to-pose movement from snapping at the keys."""
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    return u * u * (3.0 - 2.0 * u)


@dataclass(frozen=True)
class Clip:
    name: str
    category: str
    duration: float
    keys: Keys
    # A clip that only ever adds to another clip's channel (breathing under
    # everything) versus one that owns its channels (a wave replaces the idle arm).
    additive: bool = False
    # True when ending in a held pose is the point: you stay turned toward the
    # person you just turned to. Everything else must come back to rest.
    holds: bool = False
    description: str = ""

    @property
    def resources(self) -> frozenset:
        """Which body resources this clip owns.

        Two clips may overlap at the same priority only if they own different
        resources: a gaze beat (head) and an emphasis beat (arms) complement each
        other, two arm gestures do not. Non-additive clips replace exactly the
        channels they write, so this footprint is what "conflict" really means.

        Ownership is declared per clip rather than derived from every channel it
        happens to touch: a hand gesture that also nudges the head must not block
        the gaze, but a whole-body startle must.
        """
        declared = _RESOURCE_OVERRIDES.get(self.name)
        if declared:
            return frozenset(declared)
        targets = {target for _, pose in self.keys for target in pose}
        out = set()
        if targets & _HEAD_TARGETS:
            out.add("head")
        if targets & _ARM_TARGETS:
            out.add("arms")
        if targets & _BODY_TARGETS:
            out.add("body")
        return frozenset(out)

    def sample(self, t: float) -> Pose:
        """Pose at `t` seconds from the clip's own start, clamped to its length."""
        if not self.keys:
            return {}
        u = max(0.0, min(1.0, t / max(self.duration, 1e-6)))
        if u <= self.keys[0][0]:
            return _scale_pose(self.keys[0][1], 1.0)
        if u >= self.keys[-1][0]:
            return _scale_pose(self.keys[-1][1], 1.0)
        for (t0, p0), (t1, p1) in zip(self.keys, self.keys[1:]):
            if t0 <= u <= t1:
                span = (t1 - t0) or 1e-6
                w = ease((u - t0) / span)
                return _blend(p0, p1, w)
        return {}


def _scale_pose(pose: Pose, factor: float) -> Pose:
    out: Pose = {}
    for target, channels in pose.items():
        out[target] = {ch: tuple(v * factor for v in values) for ch, values in channels.items()}
    return out


def _blend(a: Pose, b: Pose, w: float) -> Pose:
    """Linear blend over the union of channels; missing channels read as rest."""
    out: Pose = {}
    for target in set(a) | set(b):
        pa, pb = a.get(target, {}), b.get(target, {})
        merged: Dict[str, Tuple[float, ...]] = {}
        for ch in set(pa) | set(pb):
            va = pa.get(ch, (0.0, 0.0, 0.0))
            vb = pb.get(ch, (0.0, 0.0, 0.0))
            if ch == "scale":
                merged[ch] = tuple(1.0 + (vb[i] - 1.0) * w if i == 0 else va[i] + (vb[i] - va[i]) * w
                                   for i in range(3))
            else:
                merged[ch] = tuple(va[i] + (vb[i] - va[i]) * w for i in range(len(va)))
        out[target] = merged
    return out


def _r(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Tuple[float, float, float]:
    return (x, y, z)


def _l(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Tuple[float, float, float]:
    return (x, y, z)


def _s(x: float = 1.0, y: float = 1.0, z: float = 1.0) -> Tuple[float, float, float]:
    return (x, y, z)


CLIPS: Dict[str, Clip] = {}


def _add(clip: Clip) -> Clip:
    CLIPS[clip.name] = clip
    return clip


# ---------------------------------------------------------------- base layer
_add(Clip(
    name="breathing", category="base", duration=2.6, additive=True,
    description="Diaphragm rise with a faint shoulder counter-motion.",
    keys=(
        (0.00, {"torso": {"loc": _l(0, 0, 0.000), "rot": _r(0, 0, 0)}}),
        (0.35, {"torso": {"loc": _l(0, 0, 0.013), "rot": _r(0, 0.010, 0)},
                "arm_l": {"rot": _r(0, 0, -0.018)}, "arm_r": {"rot": _r(0, 0, 0.018)}}),
        (0.70, {"torso": {"loc": _l(0, 0, 0.005), "rot": _r(0, 0.004, 0)}}),
        (1.00, {"torso": {"loc": _l(0, 0, 0.000), "rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="idle_natural", category="base", duration=4.2, additive=True,
    description="Weight drift plus small head repositioning; never a fixed loop.",
    keys=(
        (0.00, {"root": {"loc": _l(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
        (0.28, {"root": {"loc": _l(0.012, 0, 0)}, "torso": {"rot": _r(0.012, 0.020, 0.010)},
                 "head": {"rot": _r(-0.010, 0.030, 0.012)}}),
        (0.55, {"root": {"loc": _l(-0.006, 0, -0.004)}, "torso": {"rot": _r(-0.008, -0.014, 0)},
                 "head": {"rot": _r(0.014, -0.022, -0.010)}}),
        (0.80, {"root": {"loc": _l(0.004, 0, 0.002)}, "torso": {"rot": _r(0.006, 0.008, -0.006)},
                 "head": {"rot": _r(0, 0.012, 0.006)}}),
        (1.00, {"root": {"loc": _l(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
    ),
))

# ---------------------------------------------------------------- attention
_add(Clip(
    name="look_at_partner", category="attention", duration=0.9, holds=True,
    description="Head and torso rotate toward the other character and hold.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)}}),
        (0.45, {"head": {"rot": _r(0.02, 0.0, 0.34)}, "torso": {"rot": _r(0, 0, 0.14)}}),
        (1.00, {"head": {"rot": _r(0.02, 0.0, 0.34)}, "torso": {"rot": _r(0, 0, 0.14)}}),
    ),
))

_add(Clip(
    name="turn_toward_partner", category="attention", duration=1.2, holds=True,
    description="Whole-body turn: feet shift, torso leads, head arrives first.",
    keys=(
        (0.00, {"root": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
        (0.30, {"head": {"rot": _r(0, 0, 0.40)}, "torso": {"rot": _r(0, 0, 0.10)},
                 "root": {"rot": _r(0, 0, 0.02)}}),
        (0.70, {"head": {"rot": _r(0, 0, 0.34)}, "torso": {"rot": _r(0, 0, 0.26)},
                 "root": {"rot": _r(0, 0, 0.22)}, "arm_l": {"rot": _r(0, 0, -0.10)},
                 "arm_r": {"rot": _r(0, 0, 0.10)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0.28)}, "torso": {"rot": _r(0, 0, 0.24)},
                 "root": {"rot": _r(0, 0, 0.22)}}),
    ),
))

_add(Clip(
    name="looking_around", category="attention", duration=3.4, additive=True,
    description="Two glances away with a pupil lead, used when nobody is speaking.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}}),
        (0.22, {"head": {"rot": _r(0, 0.02, -0.20)}, "pupil_l": {"loc": _l(-0.008, 0, 0)},
                 "pupil_r": {"loc": _l(-0.008, 0, 0)}}),
        (0.40, {"head": {"rot": _r(0, 0.02, -0.16)}, "pupil_l": {"loc": _l(-0.006, 0, 0)},
                 "pupil_r": {"loc": _l(-0.006, 0, 0)}}),
        (0.70, {"head": {"rot": _r(0.03, -0.02, 0.18)}, "pupil_l": {"loc": _l(0.007, 0, 0)},
                 "pupil_r": {"loc": _l(0.007, 0, 0)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}}),
    ),
))

# ---------------------------------------------------------------- speech
_add(Clip(
    name="talk_calm", category="speech", duration=2.8, additive=True,
    description="Low, even hand emphasis; the default for plain statements.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
        (0.25, {"arm_l": {"rot": _r(-0.16, 0, -0.05)}, "elbow_l": {"rot": _r(-0.28, 0, 0)},
                 "head": {"rot": _r(0.02, 0, 0.03)}}),
        (0.50, {"arm_l": {"rot": _r(-0.05, 0, -0.02)}, "elbow_l": {"rot": _r(-0.10, 0, 0)},
                 "arm_r": {"rot": _r(-0.10, 0, 0.04)}, "elbow_r": {"rot": _r(-0.18, 0, 0)},
                 "head": {"rot": _r(-0.02, 0, -0.02)}}),
        (0.75, {"arm_r": {"rot": _r(-0.18, 0, 0.06)}, "elbow_r": {"rot": _r(-0.30, 0, 0)},
                 "head": {"rot": _r(0.03, 0, 0.02)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="talk_excited", category="speech", duration=1.7, additive=True,
    description="Higher, quicker hands with a lifted brow and forward lean.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "torso": {"rot": _r(0, 0, 0)}}),
        (0.20, {"arm_l": {"rot": _r(-0.52, 0, -0.20)}, "elbow_l": {"rot": _r(-0.70, 0, 0)},
                 "brow_l": {"loc": _l(0, 0, 0.014)}, "brow_r": {"loc": _l(0, 0, 0.014)},
                 "torso": {"rot": _r(-0.05, 0, 0)}}),
        (0.45, {"arm_r": {"rot": _r(-0.60, 0, 0.22)}, "elbow_r": {"rot": _r(-0.80, 0, 0)},
                 "wrist_r": {"rot": _r(-0.30, 0, 0)}, "torso": {"rot": _r(0.04, 0, 0.02)}}),
        (0.65, {"arm_l": {"rot": _r(-0.34, 0, -0.14)}, "elbow_l": {"rot": _r(-0.45, 0, 0)},
                 "brow_l": {"loc": _l(0, 0, 0.008)}, "brow_r": {"loc": _l(0, 0, 0.008)}}),
        (0.85, {"arm_r": {"rot": _r(-0.44, 0, 0.16)}, "elbow_r": {"rot": _r(-0.60, 0, 0)},
                 "torso": {"rot": _r(-0.03, 0, 0)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "torso": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="talk_serious", category="speech", duration=3.2, additive=True,
    description="Small, contained gestures close to the body; level head.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "elbow_l": {"rot": _r(0, 0, 0)},
                "torso": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)}}),
        (0.30, {"arm_l": {"rot": _r(-0.20, 0, -0.04)}, "elbow_l": {"rot": _r(-0.55, 0, 0.10)},
                 "brow_l": {"loc": _l(0, 0, -0.006), "rot": _r(0, 0.10, 0)},
                 "torso": {"rot": _r(0.02, 0, 0)}}),
        (0.60, {"arm_l": {"rot": _r(-0.12, 0, -0.02)}, "elbow_l": {"rot": _r(-0.35, 0, 0.05)},
                 "head": {"rot": _r(0, 0, 0.05)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "elbow_l": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="explain_with_hands", category="speech", duration=2.4,
    description="Both hands open outward in a shaping motion while talking.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_l": {"rot": _r(0, 0, 0)}, "wrist_r": {"rot": _r(0, 0, 0)}}),
        (0.25, {"arm_l": {"rot": _r(-0.44, 0, -0.22)}, "elbow_l": {"rot": _r(-0.62, 0, -0.10)},
                 "wrist_l": {"rot": _r(-0.25, 0, -0.15)},
                 "arm_r": {"rot": _r(-0.30, 0, 0.14)}, "elbow_r": {"rot": _r(-0.40, 0, 0.10)}}),
        (0.55, {"arm_l": {"rot": _r(-0.30, 0, -0.30)}, "elbow_l": {"rot": _r(-0.48, 0, -0.16)},
                 "arm_r": {"rot": _r(-0.52, 0, 0.26)}, "elbow_r": {"rot": _r(-0.70, 0, 0.16)},
                 "wrist_r": {"rot": _r(-0.30, 0, 0.20)}, "head": {"rot": _r(0.03, 0, 0.04)}}),
        (0.80, {"arm_l": {"rot": _r(-0.18, 0, -0.12)}, "elbow_l": {"rot": _r(-0.30, 0, 0)},
                 "arm_r": {"rot": _r(-0.22, 0, 0.12)}, "elbow_r": {"rot": _r(-0.34, 0, 0)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_l": {"rot": _r(0, 0, 0)}, "wrist_r": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="ask_question", category="speech", duration=1.9,
    description="Palms-up shrug with a head tilt and raised brow on the stressed syllable.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "torso": {"rot": _r(0, 0, 0)}}),
        (0.30, {"arm_l": {"rot": _r(-0.30, 0, -0.34)}, "arm_r": {"rot": _r(-0.30, 0, 0.34)},
                 "elbow_l": {"rot": _r(-0.50, 0, -0.20)}, "elbow_r": {"rot": _r(-0.50, 0, 0.20)},
                 "wrist_l": {"rot": _r(0, 0, -0.40)}, "wrist_r": {"rot": _r(0, 0, 0.40)},
                 "brow_l": {"loc": _l(0, 0, 0.016)}, "brow_r": {"loc": _l(0, 0, 0.016)},
                 "head": {"rot": _r(0, 0.06, 0.10)}, "torso": {"rot": _r(-0.03, 0, 0)}}),
        (0.70, {"arm_l": {"rot": _r(-0.24, 0, -0.28)}, "arm_r": {"rot": _r(-0.24, 0, 0.28)},
                 "elbow_l": {"rot": _r(-0.42, 0, -0.16)}, "elbow_r": {"rot": _r(-0.42, 0, 0.16)},
                 "brow_l": {"loc": _l(0, 0, 0.012)}, "brow_r": {"loc": _l(0, 0, 0.012)},
                 "head": {"rot": _r(0, 0.05, 0.08)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_l": {"rot": _r(0, 0, 0)}, "wrist_r": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="laughing", category="emotional", duration=1.6, additive=True,
    description="Shouldered bounce with a tilted head and narrowed, lowered brows.",
    keys=(
        (0.00, {"torso": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)}}),
        (0.18, {"torso": {"loc": _l(0, 0, -0.018), "rot": _r(0.06, 0, 0)},
                 "head": {"rot": _r(0.14, 0, 0)}, "brow_l": {"loc": _l(0, 0, -0.010)},
                 "brow_r": {"loc": _l(0, 0, -0.010)}, "eye_l": {"scale": _s(1, 1, 0.55)},
                 "eye_r": {"scale": _s(1, 1, 0.55)}, "mouth": {"scale": _s(1.15, 1.6, 1)}}),
        (0.38, {"torso": {"loc": _l(0, 0, 0.006), "rot": _r(-0.02, 0, 0)},
                 "head": {"rot": _r(-0.04, 0, 0.03)}, "eye_l": {"scale": _s(1, 1, 1)},
                 "eye_r": {"scale": _s(1, 1, 1)}, "mouth": {"scale": _s(1, 1, 1)}}),
        (0.58, {"torso": {"loc": _l(0, 0, -0.014), "rot": _r(0.05, 0, 0)},
                 "head": {"rot": _r(0.12, 0, -0.02)}, "brow_l": {"loc": _l(0, 0, -0.008)},
                 "brow_r": {"loc": _l(0, 0, -0.008)}, "eye_l": {"scale": _s(1, 1, 0.6)},
                 "eye_r": {"scale": _s(1, 1, 0.6)}, "mouth": {"scale": _s(1.1, 1.45, 1)},
                 "arm_l": {"rot": _r(-0.10, 0, -0.06)}, "arm_r": {"rot": _r(-0.10, 0, 0.06)}}),
        (0.80, {"torso": {"loc": _l(0, 0, 0.002), "rot": _r(0, 0, 0)},
                 "head": {"rot": _r(0, 0, 0)}, "eye_l": {"scale": _s(1, 1, 1)},
                 "eye_r": {"scale": _s(1, 1, 1)}, "mouth": {"scale": _s(1, 1, 1)}}),
        (1.00, {"torso": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)}}),
    ),
))

# ---------------------------------------------------------------- interaction
_add(Clip(
    name="greeting", category="interaction", duration=1.8,
    description="Raise the near hand to head height and hold it there briefly.",
    keys=(
        (0.00, {"arm_r": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_r": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)}}),
        (0.28, {"arm_r": {"rot": _r(-1.15, 0, 0.55)}, "elbow_r": {"rot": _r(-1.30, 0, 0)},
                 "wrist_r": {"rot": _r(-0.20, 0, 0.30)}, "head": {"rot": _r(0.05, 0, 0.10)},
                 "brow_l": {"loc": _l(0, 0, 0.014)}, "brow_r": {"loc": _l(0, 0, 0.014)}}),
        (0.60, {"arm_r": {"rot": _r(-1.20, 0, 0.60)}, "elbow_r": {"rot": _r(-1.15, 0, 0)},
                 "wrist_r": {"rot": _r(-0.30, 0, 0.35)}, "head": {"rot": _r(0.04, 0, 0.08)}}),
        (1.00, {"arm_r": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_r": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="waving", category="interaction", duration=1.5,
    description="Three wrist sweeps at a raised hand - a distinct action from greeting.",
    keys=(
        (0.00, {"arm_r": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_r": {"rot": _r(0, 0, 0)}}),
        (0.20, {"arm_r": {"rot": _r(-1.30, 0, 0.45)}, "elbow_r": {"rot": _r(-0.90, 0, 0)},
                 "wrist_r": {"rot": _r(-0.10, 0, 0.45)}}),
        (0.40, {"arm_r": {"rot": _r(-1.32, 0, 0.48)}, "elbow_r": {"rot": _r(-0.95, 0, 0)},
                 "wrist_r": {"rot": _r(0.30, 0, -0.35)}}),
        (0.58, {"arm_r": {"rot": _r(-1.28, 0, 0.42)}, "elbow_r": {"rot": _r(-0.88, 0, 0)},
                 "wrist_r": {"rot": _r(-0.20, 0, 0.40)}}),
        (0.74, {"arm_r": {"rot": _r(-1.30, 0, 0.46)}, "elbow_r": {"rot": _r(-0.92, 0, 0)},
                 "wrist_r": {"rot": _r(0.25, 0, -0.30)}}),
        (1.00, {"arm_r": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_r": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="nodding", category="interaction", duration=1.1, additive=True,
    description="Two affirmative pitches, used by the listener and for agreement.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)}}),
        (0.20, {"head": {"rot": _r(0.14, 0, 0)}, "torso": {"rot": _r(0.03, 0, 0)}}),
        (0.42, {"head": {"rot": _r(-0.03, 0, 0)}, "torso": {"rot": _r(-0.01, 0, 0)}}),
        (0.62, {"head": {"rot": _r(0.11, 0, 0)}, "torso": {"rot": _r(0.02, 0, 0)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="shaking_head", category="interaction", duration=1.3, additive=True,
    description="Two refusals with a slight brow drop.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)}}),
        (0.22, {"head": {"rot": _r(0, 0, -0.26)}, "brow_l": {"loc": _l(0, 0, -0.008)}}),
        (0.48, {"head": {"rot": _r(0, 0, 0.24)}, "brow_l": {"loc": _l(0, 0, -0.010)}}),
        (0.72, {"head": {"rot": _r(0, 0, -0.14)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="pointing", category="interaction", duration=1.6,
    description="Extend the near arm toward the partner and hold while talking.",
    keys=(
        (0.00, {"arm_r": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_r": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}}),
        (0.25, {"arm_r": {"rot": _r(-1.35, 0, 0.12)}, "elbow_r": {"rot": _r(-0.25, 0, 0)},
                 "wrist_r": {"rot": _r(-0.10, 0, 0)}, "torso": {"rot": _r(0, 0, 0.10)},
                 "head": {"rot": _r(0.02, 0, 0.12)}, "brow_r": {"loc": _l(0, 0, 0.010)}}),
        (0.70, {"arm_r": {"rot": _r(-1.42, 0, 0.10)}, "elbow_r": {"rot": _r(-0.18, 0, 0)},
                 "head": {"rot": _r(0.03, 0, 0.14)}}),
        (1.00, {"arm_r": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "wrist_r": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="shrugging", category="interaction", duration=1.2,
    description="Both shoulders lift, elbows out, palms up.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "torso": {"loc": _l(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)}}),
        (0.30, {"arm_l": {"rot": _r(-0.22, 0, -0.42)}, "arm_r": {"rot": _r(-0.22, 0, 0.42)},
                 "elbow_l": {"rot": _r(-0.85, 0, -0.25)}, "elbow_r": {"rot": _r(-0.85, 0, 0.25)},
                 "wrist_l": {"rot": _r(0, 0, -0.50)}, "wrist_r": {"rot": _r(0, 0, 0.50)},
                 "torso": {"loc": _l(0, 0, 0.012)}, "brow_l": {"loc": _l(0, 0, 0.014)},
                 "brow_r": {"loc": _l(0, 0, 0.014)}, "head": {"rot": _r(0, 0.05, 0)}}),
        (0.65, {"arm_l": {"rot": _r(-0.18, 0, -0.36)}, "arm_r": {"rot": _r(-0.18, 0, 0.36)},
                 "elbow_l": {"rot": _r(-0.75, 0, -0.20)}, "elbow_r": {"rot": _r(-0.75, 0, 0.20)},
                 "torso": {"loc": _l(0, 0, 0.010)}, "brow_l": {"loc": _l(0, 0, 0.012)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "torso": {"loc": _l(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="hand_gesture", category="interaction", duration=1.4,
    description="A single open-palm beat, the generic emphasis for a mid-sentence point.",
    keys=(
        (0.00, {"arm_l": {"rot": _r(0, 0, 0)}, "elbow_l": {"rot": _r(0, 0, 0)},
                "wrist_l": {"rot": _r(0, 0, 0)}}),
        (0.35, {"arm_l": {"rot": _r(-0.62, 0, -0.24)}, "elbow_l": {"rot": _r(-0.85, 0, -0.10)},
                 "wrist_l": {"rot": _r(-0.35, 0, -0.20)}, "head": {"rot": _r(0.02, 0, -0.05)}}),
        (0.65, {"arm_l": {"rot": _r(-0.48, 0, -0.20)}, "elbow_l": {"rot": _r(-0.60, 0, -0.08)},
                 "wrist_l": {"rot": _r(-0.15, 0, -0.10)}}),
        (1.00, {"arm_l": {"rot": _r(0, 0, 0)}, "elbow_l": {"rot": _r(0, 0, 0)},
                "wrist_l": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)}}),
    ),
))

# ---------------------------------------------------------------- emotions
_add(Clip(
    name="happy", category="emotional", duration=2.0, additive=True,
    description="Lifted chest, raised brow, head slightly up, easy sway.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0)}}),
        (0.30, {"torso": {"rot": _r(-0.04, 0, 0), "loc": _l(0, 0, 0.010)},
                 "head": {"rot": _r(-0.06, 0, 0.04)}, "brow_l": {"loc": _l(0, 0, 0.012)},
                 "brow_r": {"loc": _l(0, 0, 0.012)}, "mouth": {"scale": _s(1.12, 1.05, 1)}}),
        (0.70, {"torso": {"rot": _r(-0.03, 0, -0.02), "loc": _l(0, 0, 0.008)},
                 "head": {"rot": _r(-0.05, 0, -0.03)}, "brow_l": {"loc": _l(0, 0, 0.010)},
                 "brow_r": {"loc": _l(0, 0, 0.010)}, "mouth": {"scale": _s(1.10, 1.04, 1)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "mouth": {"scale": _s(1, 1, 1)}}),
    ),
))

_add(Clip(
    name="sad", category="emotional", duration=2.4, additive=True,
    description="Collapsed posture, downward gaze, inner brow raised.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)}}),
        (0.35, {"torso": {"rot": _r(0.08, 0, 0), "loc": _l(0, 0, -0.012)},
                 "head": {"rot": _r(0.14, 0, 0.04)}, "eye_l": {"scale": _s(1, 1, 0.80)},
                 "eye_r": {"scale": _s(1, 1, 0.80)},
                 "brow_l": {"loc": _l(0, 0, 0.006), "rot": _r(0, -0.18, 0)},
                 "brow_r": {"loc": _l(0, 0, 0.006), "rot": _r(0, 0.18, 0)}}),
        (0.75, {"torso": {"rot": _r(0.07, 0, 0), "loc": _l(0, 0, -0.010)},
                 "head": {"rot": _r(0.12, 0, 0.02)},
                 "brow_l": {"loc": _l(0, 0, 0.005), "rot": _r(0, -0.15, 0)},
                 "brow_r": {"loc": _l(0, 0, 0.005), "rot": _r(0, 0.15, 0)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "eye_l": {"scale": _s(1, 1, 1)}, "eye_r": {"scale": _s(1, 1, 1)}}),
    ),
))

_add(Clip(
    name="surprised", category="emotional", duration=1.1,
    description="Snap back with wide eyes and a dropped jaw.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)},
                "head": {"rot": _r(0, 0, 0)}, "eye_l": {"scale": _s(1, 1, 1)},
                "eye_r": {"scale": _s(1, 1, 1)}, "brow_l": {"loc": _l(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0)}, "mouth": {"scale": _s(1, 1, 1)}}),
        (0.18, {"torso": {"rot": _r(-0.05, 0, 0), "loc": _l(0, 0, 0.014)},
                 "head": {"rot": _r(-0.10, 0, 0)}, "eye_l": {"scale": _s(1.18, 1.18, 1.30)},
                 "eye_r": {"scale": _s(1.18, 1.18, 1.30)},
                 "brow_l": {"loc": _l(0, 0, 0.022)}, "brow_r": {"loc": _l(0, 0, 0.022)},
                 "mouth": {"scale": _s(0.85, 1.55, 1), "loc": _l(0, 0, -0.012)},
                 "arm_l": {"rot": _r(-0.16, 0, -0.10)}, "arm_r": {"rot": _r(-0.16, 0, 0.10)}}),
        (0.60, {"torso": {"rot": _r(-0.02, 0, 0)}, "head": {"rot": _r(-0.04, 0, 0)},
                 "eye_l": {"scale": _s(1.08, 1.08, 1.12)}, "eye_r": {"scale": _s(1.08, 1.08, 1.12)},
                 "brow_l": {"loc": _l(0, 0, 0.012)}, "brow_r": {"loc": _l(0, 0, 0.012)},
                 "mouth": {"scale": _s(0.95, 1.2, 1)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "eye_l": {"scale": _s(1, 1, 1)}, "eye_r": {"scale": _s(1, 1, 1)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "mouth": {"scale": _s(1, 1, 1), "loc": _l(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="confused", category="emotional", duration=1.8, additive=True,
    description="Head cocked to one side with an asymmetric brow.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)}}),
        (0.30, {"head": {"rot": _r(0.04, 0.10, 0.22)}, "brow_l": {"loc": _l(0, 0, 0.016)},
                 "brow_r": {"loc": _l(0, 0, -0.004), "rot": _r(0, 0.12, 0)},
                 "torso": {"rot": _r(0, 0, 0.04)}}),
        (0.70, {"head": {"rot": _r(0.03, 0.08, 0.18)}, "brow_l": {"loc": _l(0, 0, 0.012)},
                 "brow_r": {"loc": _l(0, 0, -0.003)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="angry", category="emotional", duration=1.9, additive=True,
    description="Lowered, inward brows, squared shoulders, forward tilt.",
    keys=(
        (0.00, {"brow_l": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)}}),
        (0.30, {"brow_l": {"loc": _l(0, 0, -0.014), "rot": _r(0, 0.30, 0)},
                 "brow_r": {"loc": _l(0, 0, -0.014), "rot": _r(0, -0.30, 0)},
                 "torso": {"rot": _r(-0.05, 0, 0), "loc": _l(0, 0, 0.006)},
                 "head": {"rot": _r(0.06, 0, 0)}, "eye_l": {"scale": _s(1, 1, 0.78)},
                 "eye_r": {"scale": _s(1, 1, 0.78)}, "arm_l": {"rot": _r(-0.10, 0, -0.12)},
                 "arm_r": {"rot": _r(-0.10, 0, 0.12)}}),
        (0.72, {"brow_l": {"loc": _l(0, 0, -0.012), "rot": _r(0, 0.26, 0)},
                 "brow_r": {"loc": _l(0, 0, -0.012), "rot": _r(0, -0.26, 0)},
                 "torso": {"rot": _r(-0.04, 0, 0.02)}, "eye_l": {"scale": _s(1, 1, 0.82)},
                 "eye_r": {"scale": _s(1, 1, 0.82)}}),
        (1.00, {"brow_l": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0), "rot": _r(0, 0, 0)},
                "torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "eye_l": {"scale": _s(1, 1, 1)}, "eye_r": {"scale": _s(1, 1, 1)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="curious", category="emotional", duration=1.7, additive=True,
    description="Lean in with one brow up and pupils forward.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}}),
        (0.35, {"torso": {"rot": _r(0.06, 0, 0.06)}, "head": {"rot": _r(-0.05, 0, 0.16)},
                 "brow_l": {"loc": _l(0, 0, 0.016)}, "pupil_l": {"loc": _l(0, -0.006, 0.002)},
                 "pupil_r": {"loc": _l(0, -0.006, 0.002)}, "eye_l": {"scale": _s(1.06, 1.06, 1.10)},
                 "eye_r": {"scale": _s(1.06, 1.06, 1.10)}}),
        (0.75, {"torso": {"rot": _r(0.05, 0, 0.04)}, "head": {"rot": _r(-0.04, 0, 0.12)},
                 "brow_l": {"loc": _l(0, 0, 0.012)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}, "eye_l": {"scale": _s(1, 1, 1)},
                "eye_r": {"scale": _s(1, 1, 1)}}),
    ),
))

_add(Clip(
    name="embarrassed", category="emotional", duration=2.0, additive=True,
    description="Chin down, glance away, hands draw inward.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}}),
        (0.30, {"head": {"rot": _r(0.16, 0.06, -0.22)}, "torso": {"rot": _r(0.05, 0, -0.04)},
                 "arm_l": {"rot": _r(-0.12, 0, 0.22)}, "arm_r": {"rot": _r(-0.12, 0, -0.22)},
                 "elbow_l": {"rot": _r(-0.55, 0, 0.20)}, "elbow_r": {"rot": _r(-0.55, 0, -0.20)},
                 "brow_l": {"loc": _l(0, 0, 0.010)}, "eye_l": {"scale": _s(1, 1, 0.85)},
                 "eye_r": {"scale": _s(1, 1, 0.85)},
                 "pupil_l": {"loc": _l(-0.005, 0, -0.002)}, "pupil_r": {"loc": _l(-0.005, 0, -0.002)}}),
        (0.72, {"head": {"rot": _r(0.12, 0.04, -0.16)}, "arm_l": {"rot": _r(-0.08, 0, 0.16)},
                 "arm_r": {"rot": _r(-0.08, 0, -0.16)}, "brow_l": {"loc": _l(0, 0, 0.008)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0)}, "torso": {"rot": _r(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "eye_l": {"scale": _s(1, 1, 1)},
                "eye_r": {"scale": _s(1, 1, 1)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="thinking", category="emotional", duration=2.2, additive=True,
    description="Gaze up and away, near hand to the chin, slow head drift.",
    keys=(
        (0.00, {"head": {"rot": _r(0, 0, 0)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}, "arm_l": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}}),
        (0.30, {"head": {"rot": _r(0.02, 0.04, -0.18)}, "pupil_l": {"loc": _l(0, 0, 0.006)},
                 "pupil_r": {"loc": _l(0, 0, 0.006)}, "arm_l": {"rot": _r(-0.75, 0, -0.20)},
                 "elbow_l": {"rot": _r(-1.35, 0, -0.15)}, "brow_l": {"loc": _l(0, 0, 0.008)},
                 "eye_l": {"scale": _s(1, 1, 0.90)}, "eye_r": {"scale": _s(1, 1, 0.90)}}),
        (0.70, {"head": {"rot": _r(0.01, 0.03, -0.14)}, "arm_l": {"rot": _r(-0.70, 0, -0.18)},
                 "elbow_l": {"rot": _r(-1.28, 0, -0.12)}, "pupil_l": {"loc": _l(0, 0, 0.005)},
                 "pupil_r": {"loc": _l(0, 0, 0.005)}}),
        (1.00, {"head": {"rot": _r(0, 0, 0)}, "pupil_l": {"loc": _l(0, 0, 0)},
                "pupil_r": {"loc": _l(0, 0, 0)}, "arm_l": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "brow_l": {"loc": _l(0, 0, 0)},
                "eye_l": {"scale": _s(1, 1, 1)}, "eye_r": {"scale": _s(1, 1, 1)}}),
    ),
))

_add(Clip(
    name="relaxed", category="emotional", duration=2.6, additive=True,
    description="Settled stance, slower and deeper breath, arms loose.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "arm_l": {"rot": _r(0, 0, 0)},
                "arm_r": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)}}),
        (0.40, {"torso": {"rot": _r(0.02, 0, 0.03), "loc": _l(0, 0, -0.008)},
                 "arm_l": {"rot": _r(-0.04, 0, -0.06)}, "arm_r": {"rot": _r(-0.04, 0, 0.06)},
                 "head": {"rot": _r(0.02, 0, -0.04)}, "brow_l": {"loc": _l(0, 0, -0.004)},
                 "brow_r": {"loc": _l(0, 0, -0.004)}, "eye_l": {"scale": _s(1, 1, 0.92)},
                 "eye_r": {"scale": _s(1, 1, 0.92)}}),
        (0.75, {"torso": {"rot": _r(0.01, 0, 0.02), "loc": _l(0, 0, -0.006)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "arm_l": {"rot": _r(0, 0, 0)},
                "arm_r": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "eye_l": {"scale": _s(1, 1, 1)}, "eye_r": {"scale": _s(1, 1, 1)}}),
    ),
))

_add(Clip(
    name="listen_attentive", category="speech", duration=2.2, additive=True,
    description="Still body, chin slightly up, occasional lean-in - the listener default.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}}),
        (0.30, {"torso": {"rot": _r(0.03, 0, 0.05)}, "head": {"rot": _r(-0.04, 0, 0.06)},
                 "brow_l": {"loc": _l(0, 0, 0.008)}, "eye_l": {"scale": _s(1.04, 1.04, 1.06)},
                 "eye_r": {"scale": _s(1.04, 1.04, 1.06)}, "arm_l": {"rot": _r(-0.05, 0, -0.03)},
                 "arm_r": {"rot": _r(-0.05, 0, 0.03)}}),
        (0.70, {"torso": {"rot": _r(0.02, 0, 0.03)}, "head": {"rot": _r(-0.03, 0, 0.04)},
                 "brow_l": {"loc": _l(0, 0, 0.006)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "eye_l": {"scale": _s(1, 1, 1)},
                "eye_r": {"scale": _s(1, 1, 1)}, "arm_l": {"rot": _r(0, 0, 0)},
                "arm_r": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="react_to_partner", category="interaction", duration=1.2,
    description="Short startle-and-recover beat for the moment the other one finishes.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)}}),
        (0.20, {"torso": {"rot": _r(-0.04, 0, 0), "loc": _l(0, 0, 0.010)},
                 "head": {"rot": _r(-0.06, 0, 0.08)}, "brow_l": {"loc": _l(0, 0, 0.018)},
                 "brow_r": {"loc": _l(0, 0, 0.018)}, "eye_l": {"scale": _s(1.12, 1.12, 1.20)},
                 "eye_r": {"scale": _s(1.12, 1.12, 1.20)}, "arm_l": {"rot": _r(-0.18, 0, -0.08)},
                 "arm_r": {"rot": _r(-0.18, 0, 0.08)}}),
        (0.55, {"torso": {"rot": _r(0.02, 0, 0.02)}, "head": {"rot": _r(0.03, 0, 0.04)},
                 "brow_l": {"loc": _l(0, 0, 0.006)}, "eye_l": {"scale": _s(1.04, 1.04, 1.06)},
                 "eye_r": {"scale": _s(1.04, 1.04, 1.06)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "brow_l": {"loc": _l(0, 0, 0)}, "brow_r": {"loc": _l(0, 0, 0)},
                "eye_l": {"scale": _s(1, 1, 1)}, "eye_r": {"scale": _s(1, 1, 1)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="laugh_together", category="interaction", duration=2.2, additive=True,
    description="Shared laugh: turn toward each other, bounce, hands to chest.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "mouth": {"scale": _s(1, 1, 1)}}),
        (0.22, {"torso": {"rot": _r(0.05, 0, 0.12), "loc": _l(0, 0, -0.016)},
                 "head": {"rot": _r(0.12, 0, 0.20)}, "arm_l": {"rot": _r(-0.55, 0, 0.30)},
                 "arm_r": {"rot": _r(-0.45, 0, -0.20)}, "elbow_l": {"rot": _r(-1.10, 0, 0.30)},
                 "elbow_r": {"rot": _r(-0.90, 0, -0.20)}, "mouth": {"scale": _s(1.2, 1.7, 1)},
                 "eye_l": {"scale": _s(1, 1, 0.5)}, "eye_r": {"scale": _s(1, 1, 0.5)},
                 "brow_l": {"loc": _l(0, 0, -0.008)}, "brow_r": {"loc": _l(0, 0, -0.008)}}),
        (0.48, {"torso": {"rot": _r(-0.02, 0, 0.08), "loc": _l(0, 0, 0.006)},
                 "head": {"rot": _r(-0.04, 0, 0.14)}, "mouth": {"scale": _s(1.1, 1.3, 1)},
                 "eye_l": {"scale": _s(1, 1, 0.8)}, "eye_r": {"scale": _s(1, 1, 0.8)},
                 "arm_l": {"rot": _r(-0.30, 0, 0.18)}, "elbow_l": {"rot": _r(-0.70, 0, 0.20)}}),
        (0.72, {"torso": {"rot": _r(0.04, 0, 0.10), "loc": _l(0, 0, -0.012)},
                 "head": {"rot": _r(0.10, 0, 0.18)}, "mouth": {"scale": _s(1.15, 1.55, 1)},
                 "eye_l": {"scale": _s(1, 1, 0.55)}, "eye_r": {"scale": _s(1, 1, 0.55)},
                 "arm_r": {"rot": _r(-0.40, 0, -0.16)}, "elbow_r": {"rot": _r(-0.80, 0, -0.16)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "mouth": {"scale": _s(1, 1, 1)}, "eye_l": {"scale": _s(1, 1, 1)},
                "eye_r": {"scale": _s(1, 1, 1)}, "brow_l": {"loc": _l(0, 0, 0)},
                "brow_r": {"loc": _l(0, 0, 0)}}),
    ),
))

_add(Clip(
    name="scene_end_settle", category="base", duration=1.4, additive=True,
    description="Let the pose come to rest instead of cutting to zero at the last frame.",
    keys=(
        (0.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "root": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}}),
        (0.40, {"torso": {"rot": _r(0.02, 0, 0), "loc": _l(0, 0, -0.006)},
                 "head": {"rot": _r(0.04, 0, 0)}, "arm_l": {"rot": _r(-0.06, 0, -0.04)},
                 "arm_r": {"rot": _r(-0.06, 0, 0.04)}, "elbow_l": {"rot": _r(-0.12, 0, 0)},
                 "elbow_r": {"rot": _r(-0.12, 0, 0)}}),
        (1.00, {"torso": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}, "head": {"rot": _r(0, 0, 0)},
                "arm_l": {"rot": _r(0, 0, 0)}, "arm_r": {"rot": _r(0, 0, 0)},
                "elbow_l": {"rot": _r(0, 0, 0)}, "elbow_r": {"rot": _r(0, 0, 0)},
                "root": {"rot": _r(0, 0, 0), "loc": _l(0, 0, 0)}}),
    ),
))


def clip(name: str) -> Clip:
    return CLIPS[name]


def names_in(category: str) -> List[str]:
    return [c.name for c in CLIPS.values() if c.category == category]


def all_names() -> List[str]:
    return sorted(CLIPS)
