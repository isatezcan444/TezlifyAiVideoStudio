"""Animation clip library integrity.

These tests exist because the brief forbids shipping "a few keyframes and a
sway" as animation. They check the library is actually a library: distinct
clips, real start/main/end structure, per-channel movement, and no clip that
silently collapses to rest.
"""

from __future__ import annotations

import math

import pytest

from tezlify_studio.domain.services import animation_clips as ac


REQUIRED_CATEGORIES = {"base", "attention", "speech", "emotional", "interaction"}

# The movements the brief names. A missing one is a real gap, not a rename.
REQUIRED_CLIPS = [
    "idle_natural", "breathing", "looking_around", "look_at_partner",
    "turn_toward_partner",
    "talk_calm", "talk_excited", "talk_serious", "explain_with_hands",
    "ask_question", "laughing", "listen_attentive",
    "happy", "sad", "surprised", "confused", "angry", "curious",
    "embarrassed", "thinking", "relaxed",
    "greeting", "waving", "nodding", "shaking_head", "pointing", "shrugging",
    "hand_gesture", "react_to_partner", "laugh_together",
]


def test_every_required_clip_exists():
    missing = [name for name in REQUIRED_CLIPS if name not in ac.CLIPS]
    assert not missing, f"clip library is missing: {missing}"


def test_categories_cover_the_documented_groups():
    assert {c.category for c in ac.CLIPS.values()} >= REQUIRED_CATEGORIES


@pytest.mark.parametrize("name", sorted(ac.CLIPS))
def test_clip_has_start_main_and_return_pose(name):
    """A clip must leave rest, hold, and come back - not be a single offset."""
    clip = ac.CLIPS[name]
    assert len(clip.keys) >= 3, f"{name} needs at least three pose keys"
    assert clip.keys[0][0] == pytest.approx(0.0)
    assert clip.keys[-1][0] == pytest.approx(1.0)
    assert clip.duration > 0

    peak = max(
        _magnitude(clip, t) for t in (0.15, 0.3, 0.45, 0.6, 0.75)
    )
    assert peak > 0.0, f"{name} never moves away from rest"

    # A gesture must return to rest so a limb cannot stay raised forever. Two
    # attention clips are allowed to hold, because holding *is* the action -
    # you remain turned toward the person you turned to.
    if not clip.additive and not clip.holds:
        assert _magnitude(clip, clip.duration) == pytest.approx(0.0, abs=1e-6), (
            f"{name} does not return to rest at its end"
        )


def _magnitude(clip, t: float) -> float:
    pose = clip.sample(t)
    total = 0.0
    for channels in pose.values():
        for channel, values in channels.items():
            if channel == "scale":
                total += sum(abs(v - 1.0) for v in values)
            else:
                total += sum(abs(v) for v in values)
    return total


def test_clips_are_distinguishable_from_each_other():
    """Two clips with the same sampled shape would be one clip wearing a name."""
    signature = {}
    for name, clip in ac.CLIPS.items():
        vector = tuple(
            round(_magnitude(clip, clip.duration * frac), 4)
            for frac in (0.1, 0.25, 0.5, 0.75, 0.95)
        )
        signature.setdefault(vector, []).append(name)
    duplicated = {k: v for k, v in signature.items() if len(v) > 1 and max(k) > 0.05}
    assert not duplicated, f"identical motion curves: {duplicated}"


def test_greeting_and_waving_are_different_actions():
    """Both are hand raises; if they sample the same they are one clip."""
    greet = ac.CLIPS["greeting"]
    wave = ac.CLIPS["waving"]
    wrist_greet = greet.sample(greet.duration * 0.5).get("wrist_r", {}).get("rot", (0, 0, 0))
    wrist_wave = wave.sample(wave.duration * 0.5).get("wrist_r", {}).get("rot", (0, 0, 0))
    assert wrist_greet != wrist_wave


def test_elbow_and_wrist_are_actually_driven_by_some_clips():
    """The point of repivoting the meshes is that something uses the joints."""
    users = {
        control
        for clip in ac.CLIPS.values()
        for _, pose in clip.keys
        for control in pose
        if control in ("elbow_l", "elbow_r", "wrist_l", "wrist_r")
    }
    assert users, "no clip drives an elbow or a wrist"
    assert {"elbow_l", "elbow_r"} <= users or {"elbow_l", "elbow_r"} & users


def test_speaker_clips_and_listener_clips_are_separate_sets():
    talk = {n for n, c in ac.CLIPS.items() if c.category == "speech" and n.startswith("talk")}
    listen = {n for n, c in ac.CLIPS.items() if n == "listen_attentive"}
    assert talk and listen
    assert not (talk & listen)


def test_sampling_is_clamped_outside_the_clip():
    clip = ac.CLIPS["greeting"]
    assert _magnitude(clip, -5.0) == pytest.approx(0.0)
    # Past the end a clip that returns must be back at rest, not frozen mid-wave.
    if not clip.holds:
        assert _magnitude(clip, clip.duration + 5.0) == pytest.approx(0.0)


def test_easing_is_monotonic_between_two_keys():
    """The smoothstep must not overshoot, which would pop limbs past a joint."""
    assert ac.ease(0.0) == 0.0
    assert ac.ease(1.0) == 1.0
    samples = [ac.ease(i / 40) for i in range(41)]
    assert samples == sorted(samples)
    assert all(-1e-9 <= s <= 1.0 + 1e-9 for s in samples)


def test_no_clip_produces_non_finite_values():
    for name, clip in ac.CLIPS.items():
        for frac in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            for control, channels in clip.sample(clip.duration * frac).items():
                for channel, values in channels.items():
                    assert all(math.isfinite(v) for v in values), (name, control, channel)


def test_names_in_and_all_names_agree():
    assert set(ac.all_names()) == set(ac.CLIPS)
    for category in REQUIRED_CATEGORIES:
        assert ac.names_in(category)
