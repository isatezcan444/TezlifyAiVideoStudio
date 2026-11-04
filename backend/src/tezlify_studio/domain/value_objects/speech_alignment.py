"""Speech alignment value objects (Stage 5.4).

A :class:`DialogueAlignment` is the answer to one question: *when, in seconds of
this exact audio file, is each sound actually pronounced?* The answer must come
from the audio. Timings derived from text length or from a fixed frame cycle are
not alignment, and this module keeps them distinguishable so nothing downstream
can accidentally promote an estimate into a claim.

Time reference
--------------
Every ``start_time`` / ``end_time`` here is seconds from the **start of the audio
file**, not from the start of the scene and not from the start of the dialogue's
slot inside a scene. Callers add the dialogue offset when they place the segments
on a scene timeline; keeping one single reference here is what stops offsets from
being applied twice.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tezlify_studio.domain.enums.studio_status import AlignmentSource, MouthViseme
from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidAlignmentException,
)

#: Segments closer than this are merged; below a frame of any supported fps they
#: cannot be rendered as separate mouth poses anyway.
MIN_VISIBLE_SEGMENT_SECONDS = 1.0 / 60.0

REAL_ALIGNMENT_SOURCES = frozenset(
    {AlignmentSource.CTC_FORCED, AlignmentSource.ELEVENLABS_TIMING}
)


class PhonemeSegment(BaseModel):
    """One aligned sound unit with the interval it occupies in the audio."""

    model_config = ConfigDict(extra="forbid")

    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    phoneme: str = Field(..., min_length=1, max_length=8)
    speaker_id: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: AlignmentSource = Field(default=AlignmentSource.CTC_FORCED)

    @model_validator(mode="after")
    def validate_interval(self) -> "PhonemeSegment":
        if self.end_time <= self.start_time:
            raise InvalidAlignmentException(
                f"Fonem '{self.phoneme}' için bitiş ({self.end_time}s) başlangıçtan "
                f"({self.start_time}s) büyük olmalıdır."
            )
        return self

    @property
    def duration_seconds(self) -> float:
        return round(self.end_time - self.start_time, 6)


class VisemeSegment(BaseModel):
    """A mouth shape held for an interval — the render-facing half of alignment."""

    model_config = ConfigDict(extra="forbid")

    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    viseme: MouthViseme
    phoneme: str = Field(..., min_length=1, max_length=8)
    speaker_id: str = Field(..., min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: AlignmentSource = Field(default=AlignmentSource.CTC_FORCED)

    @model_validator(mode="after")
    def validate_interval(self) -> "VisemeSegment":
        if self.end_time <= self.start_time:
            raise InvalidAlignmentException(
                f"Viseme '{self.viseme.value}' için bitiş ({self.end_time}s) başlangıçtan "
                f"({self.start_time}s) büyük olmalıdır."
            )
        return self

    @property
    def duration_seconds(self) -> float:
        return round(self.end_time - self.start_time, 6)


class AlignmentRequest(BaseModel):
    """One dialogue line to align, with the audio that was actually produced for it.

    Grouping these into a batch is what keeps the acoustic model warm: loading it
    costs seconds and over a gigabyte of RAM, so per-dialogue calls would pay that
    price once per line.
    """

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(..., min_length=1)
    speaker_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    audio_file: str = Field(..., min_length=1)
    audio_duration_seconds: float = Field(..., gt=0.0)

    def cache_key(self, model_id: str) -> str:
        """Content address binding text, audio bytes and model together.

        The audio file's contents are part of the key, so re-synthesizing a line
        invalidates its alignment instead of silently reusing stale timings.
        """
        digest = hashlib.sha256()
        try:
            with open(self.audio_file, "rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 16), b""):
                    digest.update(chunk)
        except OSError:
            # A missing file still needs a stable key; the provider will fail on it.
            digest.update(b"<unreadable>")
        digest.update(f"\x00{self.text}\x00{self.speaker_id}\x00{model_id}".encode("utf-8"))
        return digest.hexdigest()


class DialogueAlignment(BaseModel):
    """The full alignment of one dialogue line against one audio file."""

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(..., min_length=1)
    speaker_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    audio_file: str = Field(..., min_length=1)
    audio_duration_seconds: float = Field(..., gt=0.0)
    phonemes: List[PhonemeSegment] = Field(default_factory=list)
    visemes: List[VisemeSegment] = Field(default_factory=list)
    source: AlignmentSource = Field(default=AlignmentSource.CTC_FORCED)
    provider: str = Field(default="", min_length=0, max_length=80)
    model_id: Optional[str] = Field(default=None, max_length=120)
    #: Content address of (audio bytes, text, model) — the cache key and the
    #: determinism proof. Deliberately not a timestamp: re-aligning the same
    #: dialogue must produce the same record.
    fingerprint: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def validate_alignment(self) -> "DialogueAlignment":
        if self.is_real and not self.visemes:
            raise InvalidAlignmentException(
                f"'{self.dialogue_id}': gerçek alignment kaynağı ({self.source.value}) "
                "boş viseme listesi iddia edemez."
            )
        for segment in self.visemes:
            if segment.speaker_id != self.speaker_id:
                raise InvalidAlignmentException(
                    f"'{self.dialogue_id}': viseme konuşmacısı '{segment.speaker_id}' "
                    f"diyalog konuşmacısı '{self.speaker_id}' ile uyuşmuyor."
                )
        self._validate_ordering(self.phonemes, "fonem")
        self._validate_ordering(self.visemes, "viseme")
        return self

    def _validate_ordering(self, segments, label: str) -> None:
        """Reject unsorted or overlapping intervals; trailing overflow is clamped."""
        previous = None
        for segment in segments:
            if previous is not None and segment.start_time < previous.end_time - 1e-6:
                raise InvalidAlignmentException(
                    f"'{self.dialogue_id}': {label} segmentleri çakışıyor — "
                    f"{previous.end_time:.3f}s sonrası {segment.start_time:.3f}s."
                )
            previous = segment

    @property
    def is_real(self) -> bool:
        """True only when timings were measured from the audio, not guessed."""
        return self.source in REAL_ALIGNMENT_SOURCES

    @property
    def covered_seconds(self) -> float:
        return round(sum(v.duration_seconds for v in self.visemes), 6)

    @property
    def first_start_seconds(self) -> Optional[float]:
        return round(self.visemes[0].start_time, 6) if self.visemes else None

    @property
    def last_end_seconds(self) -> Optional[float]:
        return round(self.visemes[-1].end_time, 6) if self.visemes else None

    def clamped_to_audio(self) -> "DialogueAlignment":
        """Return an alignment with every interval inside the audio duration.

        A provider that runs slightly long is a rounding problem, not a render
        failure: the tail is trimmed and the rest still animates. Segments that
        start past the end are dropped rather than clamped to zero length.
        """
        kept_visemes = []
        for segment in self.visemes:
            if segment.start_time >= self.audio_duration_seconds:
                continue
            end = min(segment.end_time, self.audio_duration_seconds)
            if end <= segment.start_time:
                continue
            kept_visemes.append(segment.model_copy(update={"end_time": round(end, 6)}))
        kept_phonemes = []
        for segment in self.phonemes:
            if segment.start_time >= self.audio_duration_seconds:
                continue
            end = min(segment.end_time, self.audio_duration_seconds)
            if end <= segment.start_time:
                continue
            kept_phonemes.append(segment.model_copy(update={"end_time": round(end, 6)}))
        return self.model_copy(update={
            "visemes": kept_visemes,
            "phonemes": kept_phonemes,
        })

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
