"""Blend scheduled clips into one pose per frame.

Stdlib-only, and deliberately free of any Blender reference: this is the function
the render worker calls 30 times a second, and it is the part worth unit testing.
Keeping it here means the layering rules can be proven without launching Blender.

Layering rules, applied in priority order:

* An **additive** clip adds its channel deltas to whatever is already there. That
  is how breathing and idle sit underneath everything else without erasing a
  gesture.
* A **non-additive** clip replaces the channels it defines. Two gestures of the
  same priority never coexist because the director reserves time for them.
* Mouth channels are reserved for visemes whenever measured visemes exist, so a
  laugh beat can never overwrite real lip sync.
* Every value is scaled by the character's own profile amplitude, so the same
  clip performed by Ali and by Ayşe is not the same movement.
"""

from __future__ import annotations

from typing import Dict, Iterable, Sequence, Tuple

from tezlify_studio.domain.services.animation_clips import CLIPS
from tezlify_studio.domain.value_objects.animation_plan import (
    AnimationClipInstance,
    CharacterAnimationProfile,
)

Pose = Dict[str, Dict[str, Tuple[float, ...]]]
CHANNELS = ("rot", "loc", "scale")


def _identity(target: str) -> Dict[str, Tuple[float, ...]]:
    return {"rot": (0.0, 0.0, 0.0), "loc": (0.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0)}


def blank_pose(targets: Iterable[str]) -> Pose:
    return {target: _identity(target) for target in targets}


def scale_pose(pose: Pose, factor: float) -> Pose:
    """Amplitude-scale a pose, leaving scale channels around their 1.0 rest."""
    out: Pose = {}
    for target, channels in pose.items():
        scaled: Dict[str, Tuple[float, ...]] = {}
        for channel, values in channels.items():
            if channel == "scale":
                scaled[channel] = tuple(1.0 + (v - 1.0) * factor for v in values)
            else:
                scaled[channel] = tuple(v * factor for v in values)
        out[target] = scaled
    return out


def add_pose(target: Pose, incoming: Pose, weight: float = 1.0) -> None:
    """Accumulate `incoming` into `target` in place."""
    for name, channels in incoming.items():
        slot = target.setdefault(name, _identity(name))
        for channel, values in channels.items():
            base = slot.get(channel, (0.0, 0.0, 0.0) if channel != "scale" else (1.0, 1.0, 1.0))
            merged = []
            for index, value in enumerate(values):
                current = base[index] if index < len(base) else (0.0 if channel != "scale" else 1.0)
                if channel == "scale":
                    merged.append(current + (value - 1.0) * weight)
                else:
                    merged.append(current + value * weight)
            slot[channel] = tuple(merged)


def replace_pose(target: Pose, incoming: Pose, skip_mouth: bool = False) -> None:
    """Let a non-additive clip own the channels it writes."""
    for name, channels in incoming.items():
        if skip_mouth and name == "mouth":
            continue
        slot = target.setdefault(name, _identity(name))
        for channel, values in channels.items():
            slot[channel] = tuple(values)


def blink_at(frame: int, offset_frames: int, period: int = 96) -> float:
    """Eye-open multiplier.

    Two blinks per cycle for most people, with the second one shorter, because a
    single evenly spaced squash reads as a metronome. `offset_frames` comes from
    the character profile so two characters never blink together.
    """
    phase = (frame + offset_frames) % period
    if phase in (0, 1):
        return 0.35
    if phase == 2:
        return 0.85
    if phase in (48, 49):
        return 0.25
    if phase == 50:
        return 0.80
    return 1.0


def sample_tracks(
    instances: Sequence[AnimationClipInstance],
    profile: CharacterAnimationProfile,
    t: float,
    targets: Sequence[str],
    skip_mouth: bool = False,
) -> Pose:
    """Pose for one character at scene-relative time `t`.

    `t` is measured from the start of the scene the instances belong to. Clips
    outside their window contribute nothing, so a character returns to rest
    through the clip's own easing rather than being snapped there.
    """
    pose = blank_pose(targets)
    active = [c for c in instances if c.start <= t <= c.end]
    active.sort(key=lambda c: (c.priority, c.start))
    for instance in active:
        clip = CLIPS.get(instance.clip_name)
        if clip is None:
            continue
        sampled = clip.sample(t - instance.start)
        if not sampled:
            continue
        amplitude = profile.scale_for(instance.clip_name) * instance.weight
        shaped = scale_pose(sampled, amplitude)
        if clip.additive:
            add_pose(pose, shaped, 1.0)
        else:
            replace_pose(pose, shaped, skip_mouth)
    return pose


def apply_blink(pose: Pose, frame: int, profile: CharacterAnimationProfile) -> Pose:
    """Fold the blink curve into whatever the clips already asked the eyes to do."""
    factor = blink_at(frame, profile.blink_offset_frames)
    for eye in ("eye_l", "eye_r"):
        slot = pose.setdefault(eye, _identity(eye))
        current = slot.get("scale", (1.0, 1.0, 1.0))
        slot["scale"] = (current[0], current[1], current[2] * factor)
    return pose


def pose_delta_magnitude(pose: Pose) -> float:
    """Total movement away from rest, used by the evidence to prove motion exists."""
    total = 0.0
    for channels in pose.values():
        for channel, values in channels.items():
            if channel == "scale":
                total += sum(abs(v - 1.0) for v in values)
            else:
                total += sum(abs(v) for v in values)
    return total
