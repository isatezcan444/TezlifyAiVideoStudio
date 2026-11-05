"""Animation plan value objects.

Stdlib-only: `render_worker.py` imports this module inside Blender, which has no
pydantic. Validation is therefore explicit rather than declarative, but the rules
are the same ones the rest of the domain enforces - no negative durations, end
after start, nothing outside its scene window, and no two exclusive clips fighting
for the same control at the same time.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# Higher priority wins a shared channel. Mouth is reserved for visemes so a
# gesture can never overwrite measured lip sync.
PRIORITY_BASE = 0
PRIORITY_EMOTION = 10
PRIORITY_IDLE = 5
PRIORITY_ATTENTION = 20
PRIORITY_GESTURE = 30
PRIORITY_MOUTH = 100

SHOT_KINDS = (
    "establishing",
    "two_shot",
    "speaker_close_up",
    "listener_reaction",
    "medium_shot",
    "action_shot",
)


class AnimationPlanError(ValueError):
    pass


@dataclass(frozen=True)
class AnimationClipInstance:
    """One clip scheduled onto one character inside one scene."""

    character_id: str
    clip_name: str
    start: float
    end: float
    priority: int = PRIORITY_BASE
    weight: float = 1.0
    reason: str = ""

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise AnimationPlanError(
                f"{self.clip_name}: end {self.end} must be after start {self.start}"
            )
        if self.start < 0:
            raise AnimationPlanError(f"{self.clip_name}: negative start {self.start}")
        if not 0.0 < self.weight <= 1.0:
            raise AnimationPlanError(f"{self.clip_name}: weight {self.weight} out of range")

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class FacialExpression:
    character_id: str
    name: str
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise AnimationPlanError(f"{self.name}: end must be after start")


@dataclass(frozen=True)
class Gesture:
    character_id: str
    clip_name: str
    start: float
    end: float
    trigger: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Shot:
    kind: str
    start: float
    end: float
    focus_character_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in SHOT_KINDS:
            raise AnimationPlanError(f"unknown shot kind {self.kind!r}")
        if self.end <= self.start:
            raise AnimationPlanError(f"{self.kind}: end must be after start")


@dataclass(frozen=True)
class ShotPlan:
    scene_id: str
    shots: Tuple[Shot, ...] = ()

    def shot_at(self, t: float) -> Optional[Shot]:
        for shot in self.shots:
            if shot.start <= t < shot.end:
                return shot
        return self.shots[-1] if self.shots else None


@dataclass(frozen=True)
class CharacterAnimationProfile:
    """Per-character movement personality.

    Without this every character would perform the same clip identically, which
    is the "repetitive and mechanical" failure the brief calls out. Values are
    derived from the character id so re-rendering the same project reproduces the
    same performance.
    """

    character_id: str
    energy: float           # gesture amplitude
    gesture_rate: float     # how often a beat is taken
    posture_lean: float     # torso bias
    head_mobility: float    # head turn/tilt amplitude
    blink_offset_frames: int
    breath_period: float
    hand_bias: str          # which hand leads

    @classmethod
    def for_character(cls, character_id: str) -> "CharacterAnimationProfile":
        digest = hashlib.sha256(character_id.encode("utf-8")).digest()
        energy = 0.75 + (digest[0] % 50) / 100.0        # 0.75 .. 1.24
        gesture_rate = 0.70 + (digest[1] % 60) / 100.0  # 0.70 .. 1.29
        posture = ((digest[2] % 9) - 4) / 100.0         # -0.04 .. +0.04
        head = 0.80 + (digest[3] % 45) / 100.0          # 0.80 .. 1.24
        blink = digest[4] % 40
        breath = 2.4 + (digest[5] % 9) / 10.0           # 2.4 .. 3.2 s
        hand = "left" if digest[6] % 2 else "right"
        return cls(character_id, energy, gesture_rate, posture, head, blink, breath, hand)

    def scale_for(self, clip_name: str) -> float:
        """Amplitude multiplier for one clip, from this character's personality."""
        if clip_name in ("greeting", "waving", "pointing", "explain_with_hands",
                         "hand_gesture", "shrugging", "ask_question"):
            return self.energy
        if clip_name in ("look_at_partner", "turn_toward_partner", "nodding",
                         "shaking_head", "looking_around", "confused", "curious"):
            return self.head_mobility
        if clip_name == "breathing":
            return 1.0
        return 0.5 + self.energy / 2.0


@dataclass(frozen=True)
class SceneAnimationPlan:
    scene_id: str
    duration: float
    clips: Tuple[AnimationClipInstance, ...] = ()
    expressions: Tuple[FacialExpression, ...] = ()
    gestures: Tuple[Gesture, ...] = ()
    # Gestures the scheduler could not place because a more meaningful one
    # already owned that time. Recorded rather than silently discarded.
    dropped: Tuple[str, ...] = ()
    shot_plan: ShotPlan = field(default_factory=lambda: ShotPlan(scene_id=""))

    def clips_for(self, character_id: str) -> List[AnimationClipInstance]:
        return [c for c in self.clips if c.character_id == character_id]

    def validate(self) -> None:
        for clip in self.clips:
            if clip.end > self.duration + 1e-6:
                raise AnimationPlanError(
                    f"{self.scene_id}: clip {clip.clip_name} ends at {clip.end} "
                    f"beyond scene duration {self.duration}"
                )
        by_character: Dict[str, List[AnimationClipInstance]] = {}
        for clip in self.clips:
            by_character.setdefault(clip.character_id, []).append(clip)
        for character_id, items in by_character.items():
            exclusive = sorted(
                (c for c in items if not _clip_is_additive(c.clip_name)),
                key=lambda c: c.start,
            )
            for a, b in zip(exclusive, exclusive[1:]):
                if b.start < a.end - 1e-6 and b.priority == a.priority:
                    shared = _clip_resources(a.clip_name) & _clip_resources(b.clip_name)
                    if not shared:
                        continue
                    raise AnimationPlanError(
                        f"{self.scene_id}/{character_id}: exclusive clips "
                        f"{a.clip_name} and {b.clip_name} overlap at equal priority "
                        f"on {sorted(shared)}; one would silently overwrite the other"
                    )


@dataclass(frozen=True)
class AnimationPlan:
    """The whole production's movement schedule, one entry per scene."""

    project_id: str
    fps: int
    scenes: Tuple[SceneAnimationPlan, ...] = ()
    profiles: Dict[str, CharacterAnimationProfile] = field(default_factory=dict)

    def validate(self) -> None:
        if self.fps <= 0:
            raise AnimationPlanError(f"fps must be positive, got {self.fps}")
        for scene in self.scenes:
            scene.validate()

    def summary(self) -> Dict[str, object]:
        total = sum(len(s.clips) for s in self.scenes)
        by_clip: Dict[str, int] = {}
        for scene in self.scenes:
            for clip in scene.clips:
                by_clip[clip.clip_name] = by_clip.get(clip.clip_name, 0) + 1
        return {
            "project_id": self.project_id,
            "fps": self.fps,
            "scenes": len(self.scenes),
            "clips_total": total,
            "distinct_clips": len(by_clip),
            "clip_usage": dict(sorted(by_clip.items())),
            "gestures": sum(len(s.gestures) for s in self.scenes),
            "expressions": sum(len(s.expressions) for s in self.scenes),
            "dropped_gestures": sum(len(s.dropped) for s in self.scenes),
            "shots": [
                [{"kind": sh.kind, "focus": sh.focus_character_id,
                  "start": round(sh.start, 2), "end": round(sh.end, 2)}
                 for sh in scene.shot_plan.shots]
                for scene in self.scenes
            ],
        }


_ADDITIVE_CACHE: Dict[str, bool] = {}
_RESOURCE_CACHE: Dict[str, frozenset] = {}


def _clip_is_additive(name: str) -> bool:
    if name not in _ADDITIVE_CACHE:
        from tezlify_studio.domain.services import animation_clips

        clip = animation_clips.CLIPS.get(name)
        _ADDITIVE_CACHE[name] = bool(clip.additive) if clip else False
    return _ADDITIVE_CACHE[name]


def _clip_resources(name: str):
    if name not in _RESOURCE_CACHE:
        from tezlify_studio.domain.services import animation_clips

        clip = animation_clips.CLIPS.get(name)
        _RESOURCE_CACHE[name] = clip.resources if clip else frozenset()
    return _RESOURCE_CACHE[name]


def to_dict(plan: AnimationPlan) -> Dict[str, object]:
    """JSON-ready form, used by the render manifest and by tests."""
    return {
        "project_id": plan.project_id,
        "fps": plan.fps,
        "summary": plan.summary(),
        "profiles": {
            pid: {
                "energy": round(p.energy, 3), "gesture_rate": round(p.gesture_rate, 3),
                "posture_lean": round(p.posture_lean, 4),
                "head_mobility": round(p.head_mobility, 3),
                "blink_offset_frames": p.blink_offset_frames,
                "breath_period": round(p.breath_period, 3), "leading_hand": p.hand_bias,
            }
            for pid, p in plan.profiles.items()
        },
        "scenes": [
            {
                "scene_id": s.scene_id,
                "duration": s.duration,
                "clips": [
                    {"character_id": c.character_id, "clip": c.clip_name,
                     "start": round(c.start, 3), "end": round(c.end, 3),
                     "priority": c.priority, "weight": round(c.weight, 3),
                     "reason": c.reason}
                    for c in s.clips
                ],
                "gestures": [
                    {"character_id": g.character_id, "clip": g.clip_name,
                     "start": round(g.start, 3), "end": round(g.end, 3), "trigger": g.trigger}
                    for g in s.gestures
                ],
                "expressions": [
                    {"character_id": e.character_id, "name": e.name,
                     "start": round(e.start, 3), "end": round(e.end, 3)}
                    for e in s.expressions
                ],
                "shots": [
                    {"kind": sh.kind, "start": round(sh.start, 3), "end": round(sh.end, 3),
                     "focus": sh.focus_character_id}
                    for sh in s.shot_plan.shots
                ],
                "dropped": list(s.dropped),
            }
            for s in plan.scenes
        ],
    }
