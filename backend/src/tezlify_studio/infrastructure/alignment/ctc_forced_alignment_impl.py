"""Local CTC forced-alignment provider (Stage 5.4).

Runs the acoustic engine as a subprocess of ``tools/alignment-venv`` so the
application keeps its Python 3.14 / no-ML dependency set, and caches results by
the content of (audio bytes, transcript, model) so the same line is never aligned
twice.

Two behaviours are deliberate:

* A dialogue that cannot be aligned is **absent** from the result rather than
  returned with guessed timings. Callers fall back and say so.
* Nothing here sends audio anywhere. The model runs on the local CPU.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from typing import Dict, List, Optional

from tezlify_studio.application.ports.speech_alignment_port import SpeechAlignmentPort
from tezlify_studio.domain.enums.studio_status import AlignmentSource
from tezlify_studio.domain.services import viseme_mapper
from tezlify_studio.domain.value_objects.speech_alignment import (
    AlignmentRequest,
    DialogueAlignment,
    PhonemeSegment,
)

logger = logging.getLogger(__name__)

WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ctc_alignment_worker.py")


class CTCForcedAlignmentImpl(SpeechAlignmentPort):
    def __init__(
        self,
        python_executable: str,
        model_id: str,
        cache_dir: str,
        model_cache_dir: Optional[str] = None,
        timeout_seconds: int = 600,
        ffmpeg_executable: str = "ffmpeg",
    ):
        self.python_executable = python_executable
        self.model_id = model_id
        self.cache_dir = cache_dir
        self.model_cache_dir = model_cache_dir
        self.timeout_seconds = timeout_seconds
        self.ffmpeg_executable = ffmpeg_executable

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """True when the isolated environment and the worker script are present.

        A full import probe would cost seconds and a gigabyte of RAM on every call,
        so this stays a cheap existence check and real failures surface per batch as
        an empty result — which callers already treat as "fall back".
        """
        return bool(self.python_executable) and os.path.isfile(WORKER_SCRIPT)

    def describe(self) -> str:
        return f"local CTC forced alignment ({self.model_id})"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def align(self, requests: List[AlignmentRequest]) -> Dict[str, DialogueAlignment]:
        if not requests:
            return {}

        results: Dict[str, DialogueAlignment] = {}
        pending: List[AlignmentRequest] = []
        for request in requests:
            cached = self._load_cache(request)
            if cached is not None:
                results[request.dialogue_id] = cached
            else:
                pending.append(request)

        # Availability gates new alignment work only. A measured result already on
        # disk does not need the engine, so losing the isolated environment must
        # not throw away lip sync that was genuinely produced.
        if pending and not self.is_available():
            logger.warning(
                f"Alignment engine unavailable; {len(pending)} dialogue(s) "
                f"will use the legacy mouth animation"
            )
            return results

        if pending:
            fresh = self._run_worker(pending)
            results.update(fresh)
            for alignment in fresh.values():
                self._write_cache(alignment)

        if results:
            logger.info(
                f"Aligned {len(results)}/{len(requests)} dialogues with {self.describe()}"
            )
        else:
            logger.warning("Speech alignment produced no results; lip sync will fall back")
        return results

    # ------------------------------------------------------------------
    # Subprocess
    # ------------------------------------------------------------------
    def _run_worker(self, requests: List[AlignmentRequest]) -> Dict[str, DialogueAlignment]:
        payload = {
            "model_id": self.model_id,
            "requests": [
                {
                    "dialogue_id": request.dialogue_id,
                    "speaker_id": request.speaker_id,
                    "text": request.text,
                    # Absolute paths: the subprocess does not share this caller's
                    # working directory, and a relative path would silently miss.
                    "audio_file": os.path.abspath(os.path.expanduser(request.audio_file)),
                    "audio_duration_seconds": request.audio_duration_seconds,
                }
                for request in requests
            ],
        }

        with tempfile.TemporaryDirectory(prefix="tezlify_align_call_") as work_dir:
            request_path = os.path.join(work_dir, "request.json")
            response_path = os.path.join(work_dir, "response.json")
            with open(request_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)

            environment = dict(os.environ)
            environment["TOKENIZERS_PARALLELISM"] = "false"
            if self.model_cache_dir:
                environment["HF_HOME"] = self.model_cache_dir

            command = [self.python_executable, WORKER_SCRIPT, request_path, response_path]
            started = time.time()
            try:
                completed = subprocess.run(
                    command,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                logger.error(
                    f"Alignment worker timed out after {self.timeout_seconds}s "
                    f"for {len(requests)} dialogues"
                )
                return {}
            except OSError as exc:
                logger.error(f"Could not launch alignment worker: {exc}")
                return {}

            elapsed = time.time() - started
            if not os.path.isfile(response_path):
                logger.error(
                    f"Alignment worker wrote no response (exit {completed.returncode}) "
                    f"after {elapsed:.1f}s: {completed.stderr[-600:]}"
                )
                return {}

            try:
                with open(response_path, encoding="utf-8") as handle:
                    response = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error(f"Alignment response unreadable: {exc}")
                return {}

        if not response.get("ok"):
            logger.error(
                f"Alignment worker reported failure (exit {completed.returncode}) "
                f"after {elapsed:.1f}s: {response.get('error')} | "
                f"per-dialogue errors: {json.dumps(response.get('errors') or {}, ensure_ascii=False)[:600]} | "
                f"stderr: {completed.stderr[-600:]}"
            )
            return {}

        for dialogue_id, message in (response.get("errors") or {}).items():
            logger.warning(f"Alignment skipped for {dialogue_id}: {message}")

        alignments: Dict[str, DialogueAlignment] = {}
        by_id = {request.dialogue_id: request for request in requests}
        for dialogue_id, entry in (response.get("alignments") or {}).items():
            request = by_id.get(dialogue_id)
            if request is None:
                continue
            built = self._build_alignment(request, entry, response)
            if built is None:
                continue
            alignments[dialogue_id] = built

        logger.info(
            f"Alignment worker: {len(alignments)} dialogues in {elapsed:.1f}s "
            f"(model load {response.get('model_load_seconds', 0)}s)"
        )
        return alignments

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    def _build_alignment(
        self, request: AlignmentRequest, entry: dict, response: dict
    ) -> Optional[DialogueAlignment]:
        raw_segments = entry.get("segments") or []
        if not raw_segments:
            return None

        phonemes: List[PhonemeSegment] = []
        intervals = []
        for segment in raw_segments:
            start = float(segment.get("start_time", 0.0))
            end = float(segment.get("end_time", 0.0))
            phoneme = str(segment.get("phoneme", ""))
            if not phoneme or end <= start:
                continue
            confidence = segment.get("confidence")
            phonemes.append(PhonemeSegment(
                start_time=round(start, 6),
                end_time=round(end, 6),
                phoneme=phoneme,
                speaker_id=request.speaker_id,
                confidence=round(float(confidence), 4) if confidence is not None else None,
                source=AlignmentSource.CTC_FORCED,
            ))
            intervals.append((phoneme, start, end))

        if not phonemes:
            return None

        visemes = viseme_mapper.smooth(viseme_mapper.segments_from_intervals(
            intervals=intervals,
            speaker_id=request.speaker_id,
            source=AlignmentSource.CTC_FORCED,
            confidence=None,
        ))
        if not visemes:
            return None

        alignment = DialogueAlignment(
            dialogue_id=request.dialogue_id,
            speaker_id=request.speaker_id,
            text=request.text,
            audio_file=request.audio_file,
            audio_duration_seconds=round(request.audio_duration_seconds, 6),
            phonemes=phonemes,
            visemes=visemes,
            source=AlignmentSource.CTC_FORCED,
            provider="ctc_forced_alignment",
            model_id=str(response.get("model_id", self.model_id)),
            fingerprint=request.cache_key(self.model_id),
        )
        return alignment.clamped_to_audio()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    def _cache_path(self, request: AlignmentRequest) -> str:
        return os.path.join(self.cache_dir, f"{request.cache_key(self.model_id)}.json")

    def _load_cache(self, request: AlignmentRequest) -> Optional[DialogueAlignment]:
        path = self._cache_path(request)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            alignment = DialogueAlignment.model_validate(payload)
        except Exception as exc:
            logger.warning(f"Ignoring unreadable alignment cache {path}: {exc}")
            return None
        # A cached record whose audio disappeared is stale by definition.
        if not os.path.isfile(alignment.audio_file):
            return None
        if alignment.text != request.text or alignment.speaker_id != request.speaker_id:
            return None
        return alignment

    def _write_cache(self, alignment: DialogueAlignment) -> None:
        path = os.path.join(self.cache_dir, f"{alignment.fingerprint}.json")
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            temporary = f"{path}.tmp"
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(alignment.to_dict(), handle, ensure_ascii=False)
            os.replace(temporary, path)
        except OSError as exc:
            logger.warning(f"Could not persist alignment cache for {alignment.dialogue_id}: {exc}")
