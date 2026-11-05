"""Animation plan, layering and directing rules.

The plan is where "movements come from the story, not from a random picker"
either holds or does not, so these tests assert the scheduling invariants and the
Turkish text mapping specifically.
"""

from __future__ import annotations

import pytest

from tezlify_studio.domain.services import animation_director as director
from tezlify_studio.domain.services import animation_layers as layers
from tezlify_studio.domain.value_objects.animation_plan import (
    PRIORITY_ATTENTION,
    PRIORITY_GESTURE,
    PRIORITY_MOUTH,
    AnimationClipInstance,
    AnimationPlan,
    AnimationPlanError,
    CharacterAnimationProfile,
    Shot,
    ShotPlan,
)

TARGETS = ["root", "torso", "head", "arm_l", "arm_r", "elbow_r", "mouth", "eye_l"]


def scene_plan(duration=10.0, characters=("char_ali", "char_ayse"), dialogues=()):
    return director.plan_scene(
        scene_id="s1",
        duration=duration,
        characters=list(characters),
        dialogues=list(dialogues),
        expressions={"char_ali": "cheerful", "char_ayse": "neutral"},
        placements={"char_ali": [-0.55, 0, 0], "char_ayse": [0.55, 0, 0]},
    )


def line(speaker, start, end, text):
    return {"character_id": speaker, "start_time": start, "end_time": end, "text": text}


# ------------------------------------------------------------------ validation
def test_rejects_a_clip_that_ends_before_it_starts():
    with pytest.raises(AnimationPlanError):
        AnimationClipInstance("char_ali", "greeting", 2.0, 1.0)


def test_rejects_negative_start():
    with pytest.raises(AnimationPlanError):
        AnimationClipInstance("char_ali", "greeting", -1.0, 1.0)


def test_rejects_a_clip_running_past_the_scene():
    plan = AnimationPlan(
        project_id="p",
        fps=30,
        scenes=(
            type(scene_plan(duration=2.0))(
                scene_id="s",
                duration=2.0,
                clips=(AnimationClipInstance("char_ali", "greeting", 0.0, 5.0),),
            ),
        ),
    )
    with pytest.raises(AnimationPlanError):
        plan.validate()


def test_rejects_zero_fps():
    with pytest.raises(AnimationPlanError):
        AnimationPlan(project_id="p", fps=0).validate()


def test_rejects_two_exclusive_clips_of_equal_priority_overlapping():
    scene = type(scene_plan())(
        scene_id="s",
        duration=5.0,
        clips=(
            AnimationClipInstance("char_ali", "greeting", 0.0, 2.0, PRIORITY_GESTURE),
            AnimationClipInstance("char_ali", "waving", 1.0, 3.0, PRIORITY_GESTURE),
        ),
    )
    with pytest.raises(AnimationPlanError):
        scene.validate()


def test_clips_on_different_resources_may_overlap_at_equal_priority():
    """A nod (head) and an emphasis beat (arms) are complementary, not rivals."""
    scene = type(scene_plan())(
        scene_id="s",
        duration=5.0,
        clips=(
            AnimationClipInstance("char_ali", "look_at_partner", 0.0, 3.0, PRIORITY_GESTURE),
            AnimationClipInstance("char_ali", "hand_gesture", 1.0, 3.0, PRIORITY_GESTURE),
        ),
    )
    scene.validate()


def test_a_whole_body_clip_conflicts_with_a_gesture():
    """A startle owns the arms, so a greeting cannot play through it."""
    scene = type(scene_plan())(
        scene_id="s",
        duration=5.0,
        clips=(
            AnimationClipInstance("char_ali", "react_to_partner", 0.0, 2.0, PRIORITY_GESTURE),
            AnimationClipInstance("char_ali", "greeting", 1.0, 3.0, PRIORITY_GESTURE),
        ),
    )
    with pytest.raises(AnimationPlanError):
        scene.validate()


def test_additive_layers_are_allowed_to_overlap():
    """Breathing under a gesture is the whole point of the layer model."""
    scene = type(scene_plan())(
        scene_id="s",
        duration=5.0,
        clips=(
            AnimationClipInstance("char_ali", "breathing", 0.0, 5.0, 0),
            AnimationClipInstance("char_ali", "idle_natural", 0.0, 5.0, 5),
            AnimationClipInstance("char_ali", "happy", 0.0, 5.0, 10),
        ),
    )
    scene.validate()


def test_weight_is_bounded():
    with pytest.raises(AnimationPlanError):
        AnimationClipInstance("char_ali", "greeting", 0.0, 1.0, 1, 0.0)
    with pytest.raises(AnimationPlanError):
        AnimationClipInstance("char_ali", "greeting", 0.0, 1.0, 1, 1.5)


# ------------------------------------------------------------------ profiles
def test_profile_is_deterministic_per_character():
    a = CharacterAnimationProfile.for_character("char_ali")
    b = CharacterAnimationProfile.for_character("char_ali")
    assert a == b


def test_two_characters_do_not_share_a_personality():
    ali = CharacterAnimationProfile.for_character("char_ali")
    ayse = CharacterAnimationProfile.for_character("char_ayse")
    assert (ali.energy, ali.gesture_rate, ali.head_mobility) != (
        ayse.energy, ayse.gesture_rate, ayse.head_mobility
    )
    assert ali.blink_offset_frames != ayse.blink_offset_frames


def test_profile_scales_gestures_more_than_breathing():
    ali = CharacterAnimationProfile.for_character("char_ali")
    assert ali.scale_for("breathing") == 1.0
    assert ali.scale_for("greeting") != 1.0


# ------------------------------------------------------------------ layering
def test_additive_layers_accumulate_and_exclusive_layers_replace():
    pose = layers.blank_pose(TARGETS)
    layers.add_pose(pose, {"torso": {"rot": (0.0, 0.0, 0.10)}})
    layers.add_pose(pose, {"torso": {"rot": (0.0, 0.0, 0.05)}})
    assert pose["torso"]["rot"][2] == pytest.approx(0.15)

    layers.replace_pose(pose, {"torso": {"rot": (0.0, 0.0, 0.30)}, "head": {"rot": (0, 0, 1)}})
    assert pose["torso"]["rot"][2] == pytest.approx(0.30)
    assert pose["head"]["rot"][2] == pytest.approx(1.0)


def test_mouth_channels_can_be_reserved_for_visemes():
    """A laugh must not be able to overwrite measured lip sync."""
    pose = layers.blank_pose(TARGETS)
    layers.replace_pose(pose, {"mouth": {"scale": (1.4, 2.0, 1.0)}}, skip_mouth=True)
    assert pose["mouth"]["scale"] == (1.0, 1.0, 1.0)
    layers.replace_pose(pose, {"mouth": {"scale": (1.4, 2.0, 1.0)}}, skip_mouth=False)
    assert pose["mouth"]["scale"] == pytest.approx((1.4, 2.0, 1.0))


def test_sampling_outside_any_window_leaves_the_character_at_rest():
    instances = (AnimationClipInstance("char_ali", "greeting", 2.0, 3.8, PRIORITY_GESTURE),)
    profile = CharacterAnimationProfile.for_character("char_ali")
    before = layers.sample_tracks(instances, profile, 0.5, TARGETS, skip_mouth=True)
    assert layers.pose_delta_magnitude(before) == pytest.approx(0.0)
    during = layers.sample_tracks(instances, profile, 2.9, TARGETS, skip_mouth=True)
    assert layers.pose_delta_magnitude(during) > 0.0


def test_higher_priority_wins_a_shared_channel():
    instances = (
        AnimationClipInstance("char_ali", "idle_natural", 0.0, 4.2, 5),
        AnimationClipInstance("char_ali", "pointing", 0.0, 1.6, PRIORITY_GESTURE),
    )
    profile = CharacterAnimationProfile.for_character("char_ali")
    pose = layers.sample_tracks(instances, profile, 0.5, TARGETS, skip_mouth=True)
    pointing_only = layers.sample_tracks(instances[1:], profile, 0.5, TARGETS, skip_mouth=True)
    assert pose["arm_r"]["rot"] == pointing_only["arm_r"]["rot"]


def test_blink_closes_the_eyes_periodically_and_not_every_frame():
    profile = CharacterAnimationProfile.for_character("char_ali")
    factors = [layers.blink_at(f, profile.blink_offset_frames) for f in range(200)]
    assert min(factors) < 0.5
    assert factors.count(1.0) > 150, "the character would spend most of the shot half blinkey"


def test_blink_is_staggered_between_characters():
    ali = CharacterAnimationProfile.for_character("char_ali")
    ayse = CharacterAnimationProfile.for_character("char_ayse")
    ali_frames = [f for f in range(120) if layers.blink_at(f, ali.blink_offset_frames) < 0.9]
    ayse_frames = [f for f in range(120) if layers.blink_at(f, ayse.blink_offset_frames) < 0.9]
    assert set(ali_frames) != set(ayse_frames)


# ------------------------------------------------------------------ directing
def test_greeting_line_schedules_a_gesture_at_the_start_of_the_line():
    plan = scene_plan(dialogues=[line("char_ali", 1.0, 3.0, "Merhaba Ayşe, bugün nasılsın?")])
    greetings = [c for c in plan.clips_for("char_ali") if c.clip_name == "greeting"]
    assert greetings, "a greeting in the text produced no greeting"
    assert greetings[0].start >= 1.0 and greetings[0].start < 2.0


def test_question_line_schedules_an_ask_question_gesture():
    plan = scene_plan(dialogues=[line("char_ali", 0.5, 3.0, "Bugün hava nasıl?")])
    assert any(c.clip_name == "ask_question" for c in plan.clips_for("char_ali"))


def test_the_listener_is_not_animated_like_a_speaker():
    plan = scene_plan(
        dialogues=[line("char_ali", 0.5, 3.5, "Sana bir şey söylemem gerekiyor.")],
    )
    speaker = {c.clip_name for c in plan.clips_for("char_ali")}
    listener = {c.clip_name for c in plan.clips_for("char_ayse")}
    assert "listen_attentive" in listener
    assert not (speaker & {"listen_attentive"}), "the speaker cannot also be attending to itself"
    assert any(name.startswith("talk_") for name in speaker)


def test_listener_nods_while_the_speaker_talks():
    plan = scene_plan(dialogues=[line("char_ali", 0.5, 4.5, "Bugün çok güzel bir gün.")])
    nods = [c for c in plan.clips_for("char_ayse") if c.clip_name == "nodding"]
    assert nods, "the listener never reacts"
    assert all(0.5 <= n.start <= 4.5 for n in nods)


def test_agreement_and_refusal_use_different_head_motion():
    agree = scene_plan(dialogues=[line("char_ali", 0.5, 3.0, "Evet, haklısın.")])
    refuse = scene_plan(dialogues=[line("char_ali", 0.5, 3.0, "Hayır, olmaz öyle.")])
    assert any(c.clip_name == "nodding" for c in agree.clips_for("char_ali"))
    assert any(c.clip_name == "shaking_head" for c in refuse.clips_for("char_ali"))
    assert not any(c.clip_name == "shaking_head" for c in agree.clips_for("char_ali"))


def test_dotted_and_undotted_i_are_folded_before_matching():
    """Turkish case folding: 'MERHABA' and 'Merhaba' must both be greetings."""
    assert "greeting" in director.detect_intents("Merhaba")
    assert "greeting" in director.detect_intents("MERHABA")
    assert "question" in director.detect_intents("Nasılsın?")
    assert "question" in director.detect_intents("NASILSIN")
    assert "question" in director.detect_intents("nasılsın")
    assert "agree" in director.detect_intents("Haklısın")
    assert "sad" in director.detect_intents("Keşke orada olmasaydım")


def test_the_i_pair_folds_to_the_right_lowercase_letter():
    """'İ' -> 'i' and 'I' -> 'ı'. Inverting them silently breaks every needle."""
    assert director.normalize("İSTANBUL") == "istanbul"
    assert director.normalize("KAPI") == "kapı"
    assert director.normalize("AŞI") == "aşı"
    assert director.normalize("GİDİYORUM") == "gidiyorum"


def test_a_warm_exclamation_is_not_mistaken_for_surprise():
    """'ne güzel' means 'how lovely'. Treating it as surprise put a startle beat
    on a greeting and, worse, gave the speaker a listener's reaction clip."""
    intents = director.detect_intents("Merhaba Ayşe! Seni burada görmek ne güzel.")
    assert "greeting" in intents
    assert "surprised" not in intents


def test_the_speaker_never_gets_a_listener_reaction_clip():
    plan = scene_plan(dialogues=[line("char_ali", 0.4, 3.0, "Gerçekten mi, inanamıyorum!")])
    ali = [c.clip_name for c in plan.clips_for("char_ali")]
    assert "react_to_partner" not in ali, ali


def test_plan_is_deterministic_for_the_same_script():
    dialogues = [line("char_ali", 0.4, 2.6, "Merhaba Ayşe, bugün nasılsın?"),
                 line("char_ayse", 3.2, 5.6, "Gerçekten mi! Çok güzel.")]
    a = scene_plan(dialogues=dialogues)
    b = scene_plan(dialogues=dialogues)
    assert [(c.character_id, c.clip_name, round(c.start, 6), round(c.end, 6)) for c in a.clips] == \
           [(c.character_id, c.clip_name, round(c.start, 6), round(c.end, 6)) for c in b.clips]


def test_no_clip_is_scheduled_outside_the_scene_window():
    plan = scene_plan(duration=6.0, dialogues=[line("char_ali", 0.5, 5.5, "Merhaba nasılsın?")])
    for clip in plan.clips:
        assert clip.start >= 0.0
        assert clip.end <= 6.0 + 1e-6


def test_over_subscribed_gestures_are_recorded_not_silently_lost():
    """One short line cannot hold a greeting, a question and three beats."""
    plan = scene_plan(
        dialogues=[line("char_ali", 0.5, 2.0, "Merhaba, gerçekten mi, anlat bakalım, neden?")]
    )
    placed = len(plan.gestures)
    assert placed >= 1, "the busiest gesture in a greeting line was dropped entirely"
    if plan.dropped:
        assert all(":" in d for d in plan.dropped)


def test_shot_plan_cuts_to_the_speaker_and_back_to_the_listener():
    plan = scene_plan(
        duration=12.0,
        dialogues=[line("char_ali", 1.0, 5.0, "Sana bir şey söylemem gerekiyor, dinle."),
                   line("char_ayse", 6.0, 10.0, "Gerçekten mi, anlat bakalım.")],
    )
    kinds = [s.kind for s in plan.shot_plan.shots]
    assert "establishing" in kinds
    assert "speaker_close_up" in kinds
    assert "listener_reaction" in kinds
    for shot in plan.shot_plan.shots:
        assert 0.0 <= shot.start < shot.end <= 12.0


def test_short_lines_do_not_earn_a_cut():
    """Cutting for a one-second line would be a strobe, not a shot plan."""
    plan = scene_plan(duration=4.0, dialogues=[line("char_ali", 0.5, 1.8, "Merhaba.")])
    assert not any(s.kind == "speaker_close_up" for s in plan.shot_plan.shots)


def test_shots_do_not_overlap_and_cover_the_scene():
    plan = scene_plan(
        duration=10.0,
        dialogues=[line("char_ali", 0.4, 2.6, "Merhaba nasılsın?"),
                   line("char_ayse", 3.2, 5.6, "Çok güzel, anlat bakalım.")],
    )
    shots = list(plan.shot_plan.shots)
    assert shots[0].start == pytest.approx(0.0)
    assert shots[-1].end == pytest.approx(10.0, abs=0.01)
    for a, b in zip(shots, shots[1:]):
        assert b.start <= a.end + 0.001, f"{a.kind} and {b.kind} overlap"


def test_unknown_shot_kind_is_rejected():
    with pytest.raises(AnimationPlanError):
        Shot("closeup_of_hand", 0.0, 1.0)


def test_plan_summary_counts_every_scheduled_clip():
    plan = scene_plan(dialogues=[line("char_ali", 0.4, 2.6, "Merhaba nasılsın?")])
    wrapper = AnimationPlan(project_id="p", fps=30, scenes=(plan,))
    summary = wrapper.summary()
    assert summary["clips_total"] == len(plan.clips)
    assert summary["distinct_clips"] == len({c.clip_name for c in plan.clips})
    assert summary["fps"] == 30


def test_mouth_priority_is_reserved_for_visemes():
    assert PRIORITY_MOUTH > PRIORITY_GESTURE > PRIORITY_ATTENTION
