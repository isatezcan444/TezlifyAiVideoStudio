"""Attaches measured speech alignment to a SceneGraph (Stage 5.4).

The renderer already receives ``SceneDialogue.visemes`` through the Blender
manifest, so lip sync needs no new channel — it needs that channel to carry
timings that came from the audio, and to say honestly when it cannot.

Time reference
--------------
Alignment intervals are seconds from the start of the dialogue's own audio file.
``DialogueViseme.time`` is documented as relative to dialogue start, which is the
same thing, so values are copied without an offset. The render worker adds the
scene and dialogue offsets exactly once; adding them here too would drift the
mouth ahead of the voice by the length of everything before it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from tezlify_studio.application.ports.speech_alignment_port import SpeechAlignmentPort
from tezlify_studio.domain.enums.studio_status import AlignmentSource
from tezlify_studio.domain.value_objects.scene_graph import (
    DialogueViseme,
    SceneGraph,
)
from tezlify_studio.domain.value_objects.speech_alignment import AlignmentRequest

logger = logging.getLogger(__name__)


@dataclass
class LipSyncReport:
    """What actually happened to lip sync for one render."""

    engine: str = "none"
    enabled: bool = False
    dialogues_total: int = 0
    dialogues_with_audio: int = 0
    dialogues_aligned: int = 0
    dialogues_fallback: int = 0
    segments_total: int = 0
    mean_confidence: Optional[float] = None
    reasons: Dict[str, str] = field(default_factory=dict)

    @property
    def uses_real_alignment(self) -> bool:
        return self.dialogues_aligned > 0

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "enabled": self.enabled,
            "dialogues_total": self.dialogues_total,
            "dialogues_with_audio": self.dialogues_with_audio,
            "dialogues_aligned": self.dialogues_aligned,
            "dialogues_fallback": self.dialogues_fallback,
            "segments_total": self.segments_total,
            "mean_confidence": self.mean_confidence,
            "uses_real_alignment": self.uses_real_alignment,
            "reasons": self.reasons,
        }


class LipSyncResolver:
    def __init__(self, alignment_provider: Optional[SpeechAlignmentPort]):
        self.provider = alignment_provider

    def resolve(self, scene_graph: SceneGraph) -> tuple[SceneGraph, LipSyncReport]:
        """Return a scene graph whose dialogues carry audio-measured visemes."""
        report = LipSyncReport()
        if self.provider is None:
            report.reasons["*"] = "no alignment provider configured"
            return scene_graph, report

        report.engine = self.provider.describe()
        report.enabled = self.provider.is_available()
        if not report.enabled:
            report.reasons["*"] = (
                "alignment engine unavailable (isolated environment or model missing)"
            )
            return scene_graph, report

        requests: List[AlignmentRequest] = []
        by_id: Dict[str, tuple[str, object]] = {}
        for scene in scene_graph.scenes:
            for index, dialogue in enumerate(scene.dialogues):
                key = f"{scene.scene_id}:{index}:{dialogue.character_id}"
                report.dialogues_total += 1
                audio = dialogue.audio_file
                if not audio or not os.path.isfile(audio):
                    report.reasons[key] = "dialogue has no audio file on disk"
                    continue
                duration = self._probe_duration(audio)
                if duration is None or duration <= 0:
                    report.reasons[key] = "dialogue audio duration unreadable"
                    continue
                report.dialogues_with_audio += 1
                requests.append(AlignmentRequest(
                    dialogue_id=key,
                    speaker_id=dialogue.character_id,
                    text=dialogue.text,
                    audio_file=audio,
                    audio_duration_seconds=duration,
                ))
                by_id[key] = (scene.scene_id, dialogue)

        if not requests:
            report.reasons.setdefault("*", "no dialogue audio available to align")
            return scene_graph, report

        alignments = self.provider.align(requests)
        if not alignments:
            report.reasons["*"] = "alignment provider returned no results"
            return scene_graph, report

        updated = scene_graph.model_copy(deep=True)
        aligned_keys = set()
        confidences: List[float] = []
        for scene in updated.scenes:
            for index, dialogue in enumerate(scene.dialogues):
                key = f"{scene.scene_id}:{index}:{dialogue.character_id}"
                alignment = alignments.get(key)
                if alignment is None:
                    continue
                dialogue.visemes = [
                    DialogueViseme(
                        time=segment.start_time,
                        end_time=segment.end_time,
                        viseme=segment.viseme,
                        phoneme=segment.phoneme,
                        confidence=segment.confidence,
                        source=segment.source,
                    )
                    for segment in alignment.visemes
                ]
                aligned_keys.add(key)
                report.segments_total += len(alignment.visemes)
                # Phoneme confidence is the provider's own measure; viseme
                # confidence is always present, so fall back to it rather than
                # reporting no confidence at all.
                confidences.extend(
                    segment.confidence for segment in alignment.phonemes
                    if segment.confidence is not None
                )
                if not alignment.phonemes:
                    confidences.extend(
                        segment.confidence for segment in alignment.visemes
                        if segment.confidence is not None
                    )

        report.dialogues_aligned = len(aligned_keys)
        report.dialogues_fallback = report.dialogues_with_audio - len(aligned_keys)
        if confidences:
            report.mean_confidence = round(sum(confidences) / len(confidences), 4)
        for key in by_id:
            if key not in aligned_keys:
                report.reasons[key] = "alignment unavailable for this dialogue"

        logger.info(
            f"Lip sync: {report.dialogues_aligned}/{report.dialogues_with_audio} "
            f"dialogues aligned with {report.engine}"
        )
        return updated, report

    @staticmethod
    def _probe_duration(audio_path: str) -> Optional[float]:
        import subprocess

        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", audio_path],
                capture_output=True, text=True, timeout=30,
            )
            return float(result.stdout.strip())
        except Exception:
            return None
