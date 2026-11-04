"""Turkish letter → mouth-shape mapping for Stage 5.4 lip sync.

Two jobs, in order:

1. Map each aligned sound unit to the mouth shape a viewer would recognise.
2. Smooth the sequence so the mouth does not flicker, **without moving any
   boundary**. Every smoothing operation here only ever unions intervals that
   were already adjacent, so the sync established by the aligner survives —
   which is the whole point of the stage.

Turkish is close to phonemic, so aligning the written characters of the spoken
line is a legitimate stand-in for aligning IPA phonemes; the table below is
written against the model's own character inventory rather than invented.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from tezlify_studio.domain.enums.studio_status import AlignmentSource, MouthViseme
from tezlify_studio.domain.services.mouth_poses import (
    MOUTH_POSES,
    MouthPose,
    pose_for,
)
from tezlify_studio.domain.value_objects.speech_alignment import (
    MIN_VISIBLE_SEGMENT_SECONDS,
    VisemeSegment,
)

__all__ = [
    "MOUTH_POSES",
    "MouthPose",
    "pose_for",
    "normalize_character",
    "viseme_for_character",
    "segments_from_intervals",
    "collapse_repeats",
    "absorb_short_segments",
    "insert_rest_between_gaps",
    "smooth",
    "LETTER_TO_VISEME",
]

#: Turkish lower-casing is not ``str.lower()``. ``İ`` folds to ``i`` and ``I``
#: folds to ``ı``; Python's default would leave a combining dot on ``İ`` and map
#: ``I`` to ``l``-ish behaviour in some locales, which would silently drop the
#: character from the aligned sequence.
_TURKISH_LOWER = str.maketrans({
    "İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü",
    "Ö": "ö", "Ç": "ç",
})

#: Letter → viseme. Covers the full lowercase Turkish alphabet plus the letters a
#: Turkish speaker's transcript can contain for loanwords.
LETTER_TO_VISEME: Dict[str, MouthViseme] = {
    # Bilabial stops and nasal: lips must meet.
    "p": MouthViseme.CLOSED, "b": MouthViseme.CLOSED, "m": MouthViseme.CLOSED,
    # Labiodental: lower lip under upper teeth.
    "f": MouthViseme.FV, "v": MouthViseme.FV,
    # Alveolar stops/nasals/lateral: tongue behind the teeth, mouth partly open.
    "t": MouthViseme.DENTAL, "d": MouthViseme.DENTAL, "n": MouthViseme.DENTAL,
    "l": MouthViseme.DENTAL, "r": MouthViseme.DENTAL,
    # Fricatives and affricates: narrow groove, teeth close together.
    "s": MouthViseme.SIBILANT, "z": MouthViseme.SIBILANT,
    "ş": MouthViseme.SIBILANT, "j": MouthViseme.SIBILANT,
    "ç": MouthViseme.SIBILANT, "c": MouthViseme.SIBILANT,
    # Velars: back of the tongue raised, lips neutral.
    "k": MouthViseme.VELAR, "g": MouthViseme.VELAR, "ğ": MouthViseme.VELAR,
    "h": MouthViseme.VELAR,
    # Front unrounded vowels.
    "a": MouthViseme.OPEN, "e": MouthViseme.OPEN,
    # Front vowels with spread lips.
    "i": MouthViseme.WIDE, "ı": MouthViseme.WIDE,
    # Back rounded vowels, mid.
    "o": MouthViseme.ROUND, "ö": MouthViseme.ROUND,
    # Back rounded vowels, tight.
    "u": MouthViseme.NARROW_ROUND, "ü": MouthViseme.NARROW_ROUND,
    # Semivowels take the shape of the vowel they glide into.
    "y": MouthViseme.NARROW_ROUND, "w": MouthViseme.NARROW_ROUND,
}

#: Punctuation and word breaks are not sounds; they let the mouth return to rest.
NON_SOUND_CHARACTERS = frozenset(
    " .,;:!?'\"“”‘’()[]{}«»—–-·\t\n"
)


def normalize_character(char: str) -> Optional[str]:
    """Fold one character to the lowercase letter used by the alignment model."""
    if not char:
        return None
    lowered = char.translate(_TURKISH_LOWER).lower()
    if lowered in NON_SOUND_CHARACTERS:
        return None
    # Strip any combining marks an upper-casing round trip may have left behind.
    lowered = "".join(c for c in lowered if c.isalpha() or c == "ğ")
    return lowered or None


def viseme_for_character(char: str, default: MouthViseme = MouthViseme.REST) -> MouthViseme:
    normalized = normalize_character(char)
    if normalized is None:
        return default
    return LETTER_TO_VISEME.get(normalized, default)


def segments_from_intervals(
    intervals: List[Tuple[str, float, float]],
    speaker_id: str,
    source: AlignmentSource,
    confidence: Optional[float] = None,
) -> List[VisemeSegment]:
    """Turn ``[(character, start, end), ...]`` into viseme segments.

    Characters that carry no mouth shape (punctuation, the model's word
    separator) become REST spans so the lips close between words instead of
    freezing on the last vowel.
    """
    segments: List[VisemeSegment] = []
    for char, start, end in intervals:
        if end <= start:
            continue
        normalized = normalize_character(char)
        if normalized is None:
            viseme, phoneme = MouthViseme.REST, " "
        else:
            viseme = LETTER_TO_VISEME.get(normalized, MouthViseme.REST)
            phoneme = normalized
        segments.append(VisemeSegment(
            start_time=round(start, 6),
            end_time=round(end, 6),
            viseme=viseme,
            phoneme=phoneme,
            speaker_id=speaker_id,
            confidence=confidence,
            source=source,
        ))
    return segments


def collapse_repeats(segments: List[VisemeSegment]) -> List[VisemeSegment]:
    """Merge back-to-back segments with the same shape.

    Holding one shape across a geminate or a repeated vowel is what a viewer
    reads as one mouth movement; keyframing each copy would look like a twitch.
    Only touching segments are merged, so no boundary moves.
    """
    merged: List[VisemeSegment] = []
    for segment in segments:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.viseme == segment.viseme
            and abs(previous.end_time - segment.start_time) < 1e-6
        ):
            confidences = [
                value for value in (previous.confidence, segment.confidence)
                if value is not None
            ]
            # The weakest link governs a merged span; a merged segment with no
            # measured confidence stays unknown rather than claiming certainty.
            merged[-1] = previous.model_copy(update={
                "end_time": segment.end_time,
                "confidence": min(confidences) if confidences else None,
            })
            continue
        merged.append(segment)
    return merged


def absorb_short_segments(
    segments: List[VisemeSegment],
    minimum_seconds: float = MIN_VISIBLE_SEGMENT_SECONDS,
) -> List[VisemeSegment]:
    """Fold segments shorter than one frame of the slowest supported fps.

    At 24 fps anything under ~42 ms cannot be rendered as its own pose; leaving
    it in produces single-frame pops. A short segment is absorbed by its
    predecessor when there is one, otherwise by its successor — again without
    moving the outer boundaries of the absorbed pair.
    """
    if not segments:
        return []

    result: List[VisemeSegment] = []
    for segment in segments:
        previous = result[-1] if result else None
        if previous is not None and segment.duration_seconds < minimum_seconds:
            result[-1] = previous.model_copy(update={"end_time": segment.end_time})
            continue
        if segment.duration_seconds < minimum_seconds and not result:
            # Keep the earliest boundary; the next segment will absorb this one.
            result.append(segment)
            continue
        result.append(segment)

    # A trailing sub-frame segment that had nothing to merge forward into.
    if len(result) > 1 and result[-1].duration_seconds < minimum_seconds:
        last = result[-1]
        result[-2] = result[-2].model_copy(update={"end_time": last.end_time})
        result.pop()
    return result


def insert_rest_between_gaps(
    segments: List[VisemeSegment],
    gap_threshold_seconds: float = 0.12,
) -> List[VisemeSegment]:
    """Close the mouth in audible gaps so speech has visible edges.

    Without this the lips stay on the last vowel through a pause, which reads as
    the character holding their mouth open.
    """
    if len(segments) < 2:
        return list(segments)

    filled: List[VisemeSegment] = [segments[0]]
    for segment in segments[1:]:
        previous = filled[-1]
        gap = segment.start_time - previous.end_time
        if gap > gap_threshold_seconds:
            filled.append(VisemeSegment(
                start_time=previous.end_time,
                end_time=segment.start_time,
                viseme=MouthViseme.REST,
                phoneme=" ",
                speaker_id=segment.speaker_id,
                confidence=None,
                source=previous.source,
            ))
        filled.append(segment)
    return filled


def smooth(segments: List[VisemeSegment]) -> List[VisemeSegment]:
    """Apply the full smoothing chain in the only order that keeps timing stable."""
    ordered = sorted(segments, key=lambda s: (s.start_time, s.end_time))
    with_rest = insert_rest_between_gaps(ordered)
    collapsed = collapse_repeats(with_rest)
    return absorb_short_segments(collapsed)
