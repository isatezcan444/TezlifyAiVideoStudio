"""Stage 5.4 — Turkish phoneme/viseme mapping and mouth pose tests.

These run without the isolated alignment environment: they cover the mapping the
renderer consumes, not the acoustic engine that feeds it.
"""

import pytest

from tezlify_studio.domain.enums.studio_status import AlignmentSource, MouthViseme
from tezlify_studio.domain.services import viseme_mapper
from tezlify_studio.domain.services.mouth_poses import (
    MOUTH_POSES,
    POSE_LIMITS,
    MouthPose,
    pose_for,
)
from tezlify_studio.domain.value_objects.speech_alignment import (
    MIN_VISIBLE_SEGMENT_SECONDS,
    AlignmentRequest,
    DialogueAlignment,
    PhonemeSegment,
    VisemeSegment,
)


# ---------------------------------------------------------------------------
# The required viseme groups
# ---------------------------------------------------------------------------

def test_all_required_viseme_groups_exist():
    required = {
        "REST", "CLOSED", "FV", "DENTAL", "SIBILANT",
        "VELAR", "OPEN", "WIDE", "ROUND", "NARROW_ROUND",
    }
    assert required <= {v.value for v in MouthViseme}
    assert required <= {v.value for v in MOUTH_POSES}


@pytest.mark.parametrize(
    "letters,expected",
    [
        # p, b, m meet the lips.
        ("pbm", MouthViseme.CLOSED),
        # f, v are lip against teeth.
        ("fv", MouthViseme.FV),
        # t, d, n, l are tongue behind the teeth.
        ("tdnl", MouthViseme.DENTAL),
        # s, z, ş, j, ç are grooved fricatives/affricates.
        ("szşjc", MouthViseme.SIBILANT),
        # k, g, ğ raise the back of the tongue.
        ("kgğ", MouthViseme.VELAR),
        # a, e open the jaw.
        ("ae", MouthViseme.OPEN),
        # i, ı spread the lips.
        ("ıi", MouthViseme.WIDE),
        # o, ö round them.
        ("oö", MouthViseme.ROUND),
        # u, ü purse them.
        ("uü", MouthViseme.NARROW_ROUND),
    ],
)
def test_turkish_letters_map_to_the_expected_viseme(letters, expected):
    for letter in letters:
        assert viseme_mapper.viseme_for_character(letter) == expected, letter


def test_turkish_diacritics_are_not_dropped_or_mangled():
    for letter in "çğıöşü":
        normalized = viseme_mapper.normalize_character(letter)
        assert normalized == letter, f"{letter} folded to {normalized!r}"


@pytest.mark.parametrize(
    "upper,expected",
    [("İ", "i"), ("I", "ı"), ("Ş", "ş"), ("Ğ", "ğ"), ("Ü", "ü"), ("Ö", "ö"), ("Ç", "ç")],
)
def test_turkish_case_folding_is_correct(upper, expected):
    """Python's own ``str.lower`` leaves a combining dot on ``İ``.

    That would drop the character from the aligned sequence, so the table has to
    fold it explicitly.
    """
    assert viseme_mapper.normalize_character(upper) == expected
    assert viseme_mapper.viseme_for_character(upper) == viseme_mapper.viseme_for_character(expected)


@pytest.mark.parametrize("punctuation", [" ", ",", ".", "!", "?", ";", ":", "—", "«", "\""])
def test_punctuation_is_not_a_sound(punctuation):
    assert viseme_mapper.normalize_character(punctuation) is None
    assert viseme_mapper.viseme_for_character(punctuation) == MouthViseme.REST


def test_silence_returns_to_rest():
    assert viseme_mapper.viseme_for_character("") == MouthViseme.REST
    assert viseme_mapper.viseme_for_character("q", default=MouthViseme.REST) == MouthViseme.REST


# ---------------------------------------------------------------------------
# Segment building and smoothing
# ---------------------------------------------------------------------------

def make(intervals, source=AlignmentSource.CTC_FORCED, speaker="char_ali", confidence=None):
    return viseme_mapper.segments_from_intervals(intervals, speaker, source, confidence)


def test_segments_carry_speaker_source_and_measured_flag():
    segments = make([("a", 0.10, 0.20)], confidence=0.42)
    assert len(segments) == 1
    segment = segments[0]
    assert segment.speaker_id == "char_ali"
    assert segment.source == AlignmentSource.CTC_FORCED
    assert segment.confidence == 0.42
    assert segment.viseme == MouthViseme.OPEN
    assert segment.duration_seconds == pytest.approx(0.10)


def test_zero_and_negative_length_intervals_are_dropped():
    segments = make([("a", 0.5, 0.5), ("b", 0.7, 0.6), ("c", 0.8, 0.9)])
    assert [s.phoneme for s in segments] == ["c"]


def test_non_sound_characters_become_rest_spans():
    segments = make([("a", 0.0, 0.1), (",", 0.1, 0.2), ("b", 0.2, 0.3)])
    assert [s.viseme.value for s in segments] == ["OPEN", "REST", "CLOSED"]


def test_collapse_repeats_merges_only_touching_same_shapes():
    segments = make([("a", 0.0, 0.10), ("a", 0.10, 0.20), ("a", 0.30, 0.40)])
    merged = viseme_mapper.collapse_repeats(segments)
    assert len(merged) == 2
    assert merged[0].start_time == 0.0 and merged[0].end_time == 0.20
    assert merged[1].start_time == 0.30


def test_collapse_keeps_the_weakest_confidence():
    a, b = make([("a", 0.0, 0.1)]), make([("a", 0.1, 0.2)])
    a[0] = a[0].model_copy(update={"confidence": 0.9})
    b[0] = b[0].model_copy(update={"confidence": 0.3})
    merged = viseme_mapper.collapse_repeats(a + b)
    assert len(merged) == 1
    assert merged[0].confidence == 0.3


def test_collapse_does_not_invent_confidence():
    merged = viseme_mapper.collapse_repeats(make([("a", 0.0, 0.1), ("a", 0.1, 0.2)]))
    assert merged[0].confidence is None


def test_smoothing_never_moves_the_outer_boundaries():
    """Timing is the product. Smoothing may merge, it may not shift."""
    intervals = [("m", 0.02, 0.10), ("e", 0.10, 0.18), ("r", 0.18, 0.24),
                 ("h", 0.24, 0.30), ("a", 0.30, 0.40), ("b", 0.40, 0.46)]
    raw = make(intervals)
    smoothed = viseme_mapper.smooth(raw)
    assert smoothed[0].start_time == raw[0].start_time
    assert smoothed[-1].end_time == raw[-1].end_time
    assert smoothed[-1].end_time == 0.46
    # Adjacent identical shapes were merged, so the result is never longer.
    assert len(smoothed) <= len(raw)


def test_smoothing_produces_no_gaps_and_no_overlaps():
    raw = make([("a", 0.0, 0.1), ("a", 0.1, 0.2), ("i", 0.2, 0.5), ("u", 0.5, 0.55)])
    smoothed = viseme_mapper.smooth(raw)
    for previous, following in zip(smoothed, smoothed[1:]):
        assert following.start_time >= previous.end_time - 1e-9


def test_gap_between_words_closes_the_mouth():
    raw = make([("a", 0.0, 0.10), ("b", 0.45, 0.55)])
    with_rest = viseme_mapper.insert_rest_between_gaps(raw, gap_threshold_seconds=0.12)
    assert [s.viseme.value for s in with_rest] == ["OPEN", "REST", "CLOSED"]
    rest = with_rest[1]
    assert rest.start_time == 0.10 and rest.end_time == 0.45


def test_short_segments_are_absorbed_without_losing_the_span():
    minimum = MIN_VISIBLE_SEGMENT_SECONDS
    raw = make([("a", 0.0, 0.10), ("i", 0.10, 0.10 + minimum / 3)])
    absorbed = viseme_mapper.absorb_short_segments(raw)
    assert len(absorbed) == 1
    # Segment times are stored rounded to microseconds, so compare with tolerance.
    assert absorbed[0].end_time == pytest.approx(0.10 + minimum / 3, abs=1e-5)


def test_smooth_is_deterministic_and_order_stable():
    intervals = [("b", 0.1, 0.2), ("a", 0.0, 0.1), ("m", 0.2, 0.25)]
    first = viseme_mapper.smooth(make(intervals))
    second = viseme_mapper.smooth(make(list(reversed(intervals))))
    assert [s.model_dump() for s in first] == [s.model_dump() for s in second]


# ---------------------------------------------------------------------------
# Mouth poses
# ---------------------------------------------------------------------------

def test_every_viseme_group_has_a_pose():
    for viseme in MouthViseme:
        assert viseme in MOUTH_POSES


def test_poses_stay_inside_the_declared_limits():
    for viseme, pose in MOUTH_POSES.items():
        clamped = pose_for(viseme)
        assert POSE_LIMITS["width_scale"][0] <= clamped.width_scale <= POSE_LIMITS["width_scale"][1]
        assert POSE_LIMITS["open_scale"][0] <= clamped.open_scale <= POSE_LIMITS["open_scale"][1]
        assert POSE_LIMITS["jaw_offset"][0] <= clamped.jaw_offset <= POSE_LIMITS["jaw_offset"][1]


def test_rest_pose_is_the_identity_transform():
    pose = pose_for(MouthViseme.REST)
    assert (pose.width_scale, pose.open_scale, pose.jaw_offset) == (1.0, 1.0, 0.0)


def test_closed_is_narrower_than_open_and_open_drops_the_jaw_furthest():
    closed, opened = pose_for(MouthViseme.CLOSED), pose_for(MouthViseme.OPEN)
    assert closed.open_scale < 1.0 < opened.open_scale
    assert closed.jaw_offset > opened.jaw_offset
    deepest = min(pose_for(v).jaw_offset for v in MouthViseme)
    assert deepest == opened.jaw_offset


def test_rounded_vowels_narrow_the_mouth_and_wide_vowels_spread_it():
    assert pose_for(MouthViseme.ROUND).width_scale < 1.0
    assert pose_for(MouthViseme.NARROW_ROUND).width_scale < pose_for(MouthViseme.ROUND).width_scale
    assert pose_for(MouthViseme.WIDE).width_scale > 1.0
    assert pose_for(MouthViseme.SIBILANT).width_scale > 1.0


def test_pose_for_accepts_manifest_strings_and_falls_back_to_rest():
    assert pose_for("OPEN") == pose_for(MouthViseme.OPEN)
    assert pose_for("NOT_A_VISEME") == pose_for(MouthViseme.REST)
    assert pose_for(None) == pose_for(MouthViseme.REST)


def test_poses_are_pairwise_distinct():
    """Ten poses that render identically would be a fake viseme set."""
    poses = [pose_for(v) for v in MouthViseme]
    signatures = {(p.width_scale, p.open_scale, p.jaw_offset) for p in poses}
    assert len(signatures) == len(poses)


# ---------------------------------------------------------------------------
# Alignment value objects
# ---------------------------------------------------------------------------

def build(**overrides):
    base = dict(
        dialogue_id="d1",
        speaker_id="char_ali",
        text="Merhaba",
        audio_file="/tmp/x.mp3",
        audio_duration_seconds=2.0,
    )
    base.update(overrides)
    return base


def test_negative_or_reversed_interval_is_rejected():
    with pytest.raises(Exception):
        PhonemeSegment(start_time=0.5, end_time=0.5, phoneme="a", speaker_id="c")
    with pytest.raises(Exception):
        VisemeSegment(start_time=0.5, end_time=0.4, viseme=MouthViseme.OPEN,
                      phoneme="a", speaker_id="c")


def test_overlapping_visemes_are_rejected():
    with pytest.raises(Exception):
        DialogueAlignment(
            **build(),
            visemes=[
                VisemeSegment(start_time=0.1, end_time=0.3, viseme=MouthViseme.OPEN,
                              phoneme="a", speaker_id="char_ali"),
                VisemeSegment(start_time=0.2, end_time=0.4, viseme=MouthViseme.CLOSED,
                              phoneme="b", speaker_id="char_ali"),
            ],
        )


def test_speaker_mismatch_between_alignment_and_segment_is_rejected():
    with pytest.raises(Exception):
        DialogueAlignment(
            **build(speaker_id="char_ali"),
            visemes=[VisemeSegment(start_time=0.1, end_time=0.2, viseme=MouthViseme.OPEN,
                                   phoneme="a", speaker_id="char_ayse")],
        )


def test_empty_alignment_is_allowed_but_not_as_real_measurement():
    """A broken/empty alignment must not crash, and must not claim to be measured."""
    empty = DialogueAlignment(**build(source=AlignmentSource.ESTIMATED))
    assert empty.visemes == []
    assert empty.is_real is False
    assert empty.first_start_seconds is None
    assert empty.covered_seconds == 0.0

    with pytest.raises(Exception):
        DialogueAlignment(**build(source=AlignmentSource.CTC_FORCED, visemes=[]))


def test_segments_past_the_audio_end_are_trimmed_not_fatal():
    """Overrunning the audio is a rounding problem; overlapping intervals are not."""
    alignment = DialogueAlignment(
        **build(audio_duration_seconds=1.0),
        phonemes=[PhonemeSegment(start_time=0.9, end_time=1.4, phoneme="a", speaker_id="char_ali")],
        visemes=[
            VisemeSegment(start_time=0.5, end_time=1.1, viseme=MouthViseme.OPEN,
                          phoneme="a", speaker_id="char_ali"),
            VisemeSegment(start_time=1.2, end_time=1.6, viseme=MouthViseme.CLOSED,
                          phoneme="b", speaker_id="char_ali"),
        ],
    )
    clamped = alignment.clamped_to_audio()
    assert clamped.last_end_seconds == pytest.approx(1.0)
    # The segment that started past the end is dropped rather than squeezed.
    assert [v.phoneme for v in clamped.visemes] == ["a"]
    assert clamped.visemes[0].end_time == pytest.approx(1.0)
    assert clamped.phonemes[0].end_time == pytest.approx(1.0)


def test_overlapping_segments_cannot_be_clamped_into_existence():
    """Overlap is rejected at construction, so a corrupt alignment never renders."""
    with pytest.raises(Exception):
        DialogueAlignment(
            **build(audio_duration_seconds=1.0),
            visemes=[
                VisemeSegment(start_time=0.1, end_time=0.6, viseme=MouthViseme.OPEN,
                              phoneme="a", speaker_id="char_ali"),
                VisemeSegment(start_time=0.4, end_time=0.9, viseme=MouthViseme.CLOSED,
                              phoneme="b", speaker_id="char_ali"),
            ],
        )


def test_only_real_providers_report_is_real():
    segment = [VisemeSegment(start_time=0.0, end_time=0.1, viseme=MouthViseme.OPEN,
                             phoneme="a", speaker_id="char_ali")]
    for source, expected in (
        (AlignmentSource.CTC_FORCED, True),
        (AlignmentSource.ELEVENLABS_TIMING, True),
        (AlignmentSource.ESTIMATED, False),
        (AlignmentSource.LEGACY_FLAP, False),
    ):
        alignment = DialogueAlignment(**build(source=source), visemes=[
            s.model_copy(update={"source": source}) for s in segment
        ])
        assert alignment.is_real is expected, source


def test_cache_key_is_content_addressed_and_stable(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"speech-bytes")
    request = AlignmentRequest(
        dialogue_id="d1", speaker_id="char_ali", text="Merhaba",
        audio_file=str(audio), audio_duration_seconds=2.0,
    )
    assert request.cache_key("model-x") == request.cache_key("model-x")
    assert request.cache_key("model-x") != request.cache_key("model-y")

    changed_text = request.model_copy(update={"text": "Merhaba!"})
    assert changed_text.cache_key("model-x") != request.cache_key("model-x")

    # Re-synthesising the line must invalidate the alignment, not reuse it.
    before_rewrite = request.cache_key("model-x")
    audio.write_bytes(b"different-speech-bytes")
    assert request.cache_key("model-x") != before_rewrite


def test_cache_key_survives_a_missing_audio_file(tmp_path):
    request = AlignmentRequest(
        dialogue_id="d1", speaker_id="char_ali", text="Merhaba",
        audio_file=str(tmp_path / "absent.mp3"), audio_duration_seconds=2.0,
    )
    assert len(request.cache_key("model-x")) == 64


def test_alignment_roundtrips_through_json():
    alignment = DialogueAlignment(
        **build(),
        phonemes=[PhonemeSegment(start_time=0.0, end_time=0.1, phoneme="m",
                                 speaker_id="char_ali", confidence=0.31)],
        visemes=[VisemeSegment(start_time=0.0, end_time=0.1, viseme=MouthViseme.CLOSED,
                               phoneme="m", speaker_id="char_ali", confidence=0.31)],
    )
    restored = DialogueAlignment.model_validate(alignment.to_dict())
    assert restored.model_dump() == alignment.model_dump()
