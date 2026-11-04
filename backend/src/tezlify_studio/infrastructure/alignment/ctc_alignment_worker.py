#!/usr/bin/env python3
"""CTC forced-alignment worker — runs in tools/alignment-venv, never in the app venv.

The application venv is Python 3.14 with a deliberately small dependency set
(fastapi/sqlalchemy/pydantic). Torch and transformers belong to neither, so this
script is launched as a subprocess by
``infrastructure/alignment/ctc_forced_alignment_impl.py`` and talks to it only
through two JSON files.

It returns *sound* intervals. Mapping them to mouth shapes is domain logic and
lives in ``domain/services/viseme_mapper.py``, so the acoustic engine stays
replaceable.

Usage:
    alignment-venv/bin/python ctc_alignment_worker.py <request.json> <response.json>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

# Heavy imports are deliberately last: if they are missing we must still be able to
# answer the parent process with a structured "unavailable" instead of a traceback.
REQUEST_PATH = sys.argv[1] if len(sys.argv) > 1 else ""
RESPONSE_PATH = sys.argv[2] if len(sys.argv) > 2 else ""

SAMPLE_RATE = 16000
WORD_SEPARATOR = "|"


def emit(payload: dict) -> None:
    with open(RESPONSE_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def log(message: str) -> None:
    print(f"[ALIGN_WORKER] {message}", flush=True)


def decode_to_pcm16k(audio_file: str, work_dir: str) -> str:
    """Resample any input (mp3/aiff/wav) to 16 kHz mono wav with FFmpeg.

    The dialogue assets in this project are MP3, and libsndfile's MP3 support is
    not something to depend on silently; FFmpeg is already a hard requirement of
    the render pipeline.
    """
    target = os.path.join(work_dir, "decoded.wav")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", audio_file,
            "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", target,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not os.path.isfile(target):
        raise RuntimeError(f"FFmpeg decode failed: {result.stderr[-400:]}")
    return target


def build_char_list(tokenizer, class_count: int):
    """Vocabulary indexed by token id, matching the logits' class axis exactly.

    ctc_segmentation uses ``char_list.index(symbol)`` to build the ground-truth
    matrix, so any entry missing or out of position mislabels every later frame.
    Special tokens keep their slot with an empty label because only their index
    matters; the blank is the id that dominates silence, which for this model is
    ``[PAD]`` rather than the conventional 0.
    """
    vocab = tokenizer.get_vocab()
    by_index = {}
    for token, index in vocab.items():
        index = int(index)
        if len(token) == 1 or token in ("|", "·"):
            by_index[index] = token
    char_list = [by_index.get(i, "") for i in range(class_count)]
    return char_list, int(tokenizer.pad_token_id)


def align_one(config, model, processor, char_list, blank, wav_path: str, text: str):
    """Align one known transcript to one audio file and return timed characters.

    Returns ``(segments, diagnostics)`` where segments is
    ``[(character, start_seconds, end_seconds, confidence), ...]``.
    """
    import numpy as np
    import soundfile as sf
    import torch
    from ctc_segmentation import ctc_segmentation, prepare_tokenized_text

    audio, rate = sf.read(wav_path)
    if rate != SAMPLE_RATE:
        raise RuntimeError(f"decoded audio came back at {rate} Hz, expected {SAMPLE_RATE}")
    duration = len(audio) / rate

    lowered = text.translate(str.maketrans({"İ": "i", "I": "ı"})).lower()
    allowed = set(char_list)
    symbols = []
    pending_break = False
    for char in lowered:
        if char.isspace():
            pending_break = True
            continue
        if char not in allowed:
            continue
        if pending_break and symbols and symbols[-1] != WORD_SEPARATOR:
            symbols.append(WORD_SEPARATOR)
        pending_break = False
        symbols.append(char)
    if not symbols:
        raise RuntimeError("no alignable characters after normalization")

    inputs = processor(np.asarray(audio, dtype=np.float32),
                       sampling_rate=SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
        posteriors = torch.softmax(logits, dim=-1)[0]

    matrix = posteriors.detach().numpy().astype(np.float64)
    if matrix.shape[1] != len(char_list):
        raise RuntimeError(
            f"logits class axis {matrix.shape[1]} != char_list {len(char_list)}"
        )

    tokenized, utt_begin = prepare_tokenized_text(config, [" ".join(symbols)])
    timings, _char_probs, _state = ctc_segmentation(config, matrix, tokenized)

    # timings[i] is already in seconds: the backtracker stores
    # (offsets[c] + t) * index_duration_in_seconds per ground-truth symbol, so a
    # character owns the span up to the next symbol.
    first = utt_begin[0] + 1  # the helper prefixes a word break before token 0
    index_seconds = config.index_duration_in_seconds
    segments = []
    for offset, symbol in enumerate(symbols):
        position = first + offset
        if symbol == WORD_SEPARATOR:
            continue
        start = float(timings[position])
        end = float(timings[position + 1]) if position + 1 < len(timings) else duration
        if end <= start:
            continue
        start = max(0.0, min(start, duration))
        end = max(0.0, min(end, duration))
        if end <= start:
            continue
        lo = max(0, int(round(start / index_seconds)))
        hi = min(matrix.shape[0], int(round(end / index_seconds)) + 1)
        class_index = char_list.index(symbol)
        confidence = float(matrix[lo:hi, class_index].mean()) if hi > lo else 0.0
        segments.append((symbol, round(start, 4), round(end, 4), round(confidence, 4)))

    diagnostics = {
        "audio_duration_seconds": round(duration, 4),
        "frame_count": int(matrix.shape[0]),
        "frame_ms": round(1000.0 * duration / max(1, matrix.shape[0]), 3),
        "aligned_characters": len(segments),
    }
    return segments, diagnostics


def main() -> int:
    if not REQUEST_PATH or not RESPONSE_PATH:
        emit({"ok": False, "error": "usage: ctc_alignment_worker.py <request> <response>"})
        return 2

    with open(REQUEST_PATH, encoding="utf-8") as handle:
        request = json.load(handle)

    model_id = request.get("model_id")
    requests = request.get("requests", [])
    if not model_id or not requests:
        emit({"ok": False, "error": "request needs model_id and requests"})
        return 2

    try:
        import numpy as np  # noqa: F401
        import torch  # noqa: F401
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        from ctc_segmentation import CtcSegmentationParameters
    except Exception as exc:
        emit({
            "ok": False,
            "unavailable": True,
            "error": f"alignment dependencies missing in isolated env: {exc}",
        })
        return 3

    load_start = time.time()
    try:
        processor = Wav2Vec2Processor.from_pretrained(model_id)
        model = Wav2Vec2ForCTC.from_pretrained(model_id)
        model.eval()
    except Exception as exc:
        emit({
            "ok": False,
            "unavailable": True,
            "error": f"could not load acoustic model {model_id}: {exc}",
        })
        return 4

    class_count = int(model.config.vocab_size)
    char_list, blank = build_char_list(processor.tokenizer, class_count)
    config = CtcSegmentationParameters(
        char_list=char_list,
        blank=blank,
        space=WORD_SEPARATOR,
        index_duration=0.02,
        start_of_ground_truth=WORD_SEPARATOR,
        excluded_characters=".,»«•❍·",
        tokenized_meta_symbol=WORD_SEPARATOR,
    )
    log(
        f"model {model_id} loaded in {time.time() - load_start:.1f}s "
        f"(vocab={class_count}, blank={blank})"
    )

    alignments = {}
    errors = {}
    with tempfile.TemporaryDirectory(prefix="tezlify_align_") as work_dir:
        for item in requests:
            dialogue_id = item["dialogue_id"]
            started = time.time()
            try:
                wav_path = decode_to_pcm16k(item["audio_file"], work_dir)
                segments, diagnostics = align_one(
                    config, model, processor, char_list, blank,
                    wav_path, item["text"],
                )
                if not segments:
                    raise RuntimeError("alignment produced no timed characters")
                alignments[dialogue_id] = {
                    "segments": [
                        {"phoneme": symbol, "start_time": start, "end_time": end,
                         "confidence": confidence}
                        for symbol, start, end, confidence in segments
                    ],
                    "diagnostics": diagnostics,
                    "elapsed_seconds": round(time.time() - started, 3),
                }
                log(
                    f"{dialogue_id}: {len(segments)} chars in "
                    f"{time.time() - started:.2f}s"
                )
            except Exception as exc:
                errors[dialogue_id] = f"{type(exc).__name__}: {exc}"
                log(f"{dialogue_id} FAILED: {exc}")

    emit({
        "ok": bool(alignments),
        "engine": "ctc_forced_alignment",
        "model_id": model_id,
        "blank_index": blank,
        "sample_rate": SAMPLE_RATE,
        "model_load_seconds": round(time.time() - load_start, 3),
        "alignments": alignments,
        "errors": errors,
    })
    return 0 if alignments else 1


if __name__ == "__main__":
    raise SystemExit(main())
