#!/usr/bin/env python3
"""Feasibility probe: real Turkish character-level forced alignment, locally.

Runs inside tools/alignment-venv (python3.12) — never inside the application venv.
Nothing here is production code; it exists to answer one question with evidence:
can this machine align Turkish audio to per-character intervals without sending
audio to any server?

It also reports the model's own transcription accuracy, because an aligner that
cannot recognise the speech cannot place its sounds in time.

Usage:
    tools/alignment-venv/bin/python tools/alignment_probe/probe_ctc.py
"""

from __future__ import annotations

import json
import os
import time

os.environ.setdefault(
    "HF_HOME", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "hf-cache"))
)

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor  # noqa: E402
from ctc_segmentation import (  # noqa: E402
    CtcSegmentationParameters,
    ctc_segmentation,
    prepare_tokenized_text,
)

MODEL_ID = "Baybars/wav2vec2-xls-r-300m-cv8-turkish"
PROBE_DIR = os.path.dirname(os.path.abspath(__file__))
SENTENCES = json.load(open(os.path.join(PROBE_DIR, "sentences.json"), encoding="utf-8"))

WORD_SEPARATOR = "|"  # this model's own in-vocabulary word boundary


def build_char_list(tokenizer, class_count: int) -> tuple[list[str], int]:
    """Vocabulary ordered by token id, padded to the logits' class axis.

    ctc_segmentation indexes this list directly with the class axis of the
    posterior matrix, so a missing or reordered entry silently misaligns
    everything. Special tokens keep their slot with an empty label; only their
    indices matter. The blank is the id that dominates the argmax of silence,
    which for this model is `[PAD]` = 38.
    """
    vocab = tokenizer.get_vocab()
    by_index = {}
    for token, index in vocab.items():
        index = int(index)
        if len(token) == 1:
            by_index[index] = token
        elif token in ("|", "·"):
            by_index[index] = token
    char_list = [by_index.get(i, "") for i in range(class_count)]
    blank = tokenizer.pad_token_id
    assert blank < class_count, f"blank id {blank} outside class axis {class_count}"
    return char_list, int(blank)


def ctc_greedy_decode(ids, blank: int) -> str:
    """Collapse repeats then drop blanks — the CTC decode the HF helper does not do."""
    out = []
    previous = None
    for raw in ids:
        index = int(raw)
        if index == previous:
            continue
        previous = index
        if index != blank:
            out.append(index)
    return out


def normalize(text: str, char_list: list[str]) -> tuple[str, list[int]]:
    """Keep only in-vocabulary characters, lowercased Turkish-style, and trace them."""
    lowered = text.translate(str.maketrans({"İ": "i", "I": "ı"})).lower()
    allowed = set(char_list)
    chars: list[str] = []
    sources: list[int] = []
    word_break_pending = False
    for index, char in enumerate(lowered):
        if char.isspace():
            word_break_pending = True
            continue
        if char not in allowed:
            continue
        if word_break_pending and chars and chars[-1] != WORD_SEPARATOR:
            chars.append(WORD_SEPARATOR)
            sources.append(index)
        word_break_pending = False
        chars.append(char)
        sources.append(index)
    return "".join(chars), sources


def main() -> int:
    print(f"loading {MODEL_ID} ...", flush=True)
    load_start = time.time()
    processor = Wav2Vec2Processor.from_pretrained(MODEL_ID)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL_ID)
    model.eval()
    print(f"loaded in {time.time() - load_start:.1f}s", flush=True)

    tokenizer = processor.tokenizer
    class_count = int(model.config.vocab_size)
    char_list, blank = build_char_list(tokenizer, class_count)
    print(f"char_list size={len(char_list)} blank={blank} ('{char_list[blank]}')", flush=True)
    print(f"chars: {''.join(c for c in char_list if c)}", flush=True)

    config = CtcSegmentationParameters(
        char_list=char_list,
        blank=blank,
        space=WORD_SEPARATOR,
        index_duration=0.02,
        start_of_ground_truth=WORD_SEPARATOR,
        excluded_characters=".,»«•❍·",
        tokenized_meta_symbol=WORD_SEPARATOR,
    )

    results = []
    for item in SENTENCES:
        audio, rate = sf.read(item["wav"])
        duration = len(audio) / rate
        sequence, sources = normalize(item["text"], char_list)
        print(f"\n--- s{item['id']}: {item['text']!r}")
        print(f"    aligned sequence: {sequence!r} ({len(sequence)} tokens)")

        inputs = processor(
            np.asarray(audio, dtype=np.float32), sampling_rate=rate, return_tensors="pt"
        )
        infer_start = time.time()
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        infer_seconds = time.time() - infer_start
        # ctc_segmentation wants (time, class); the model emits (batch, time, class).
        matrix = probs[0].detach().numpy().astype(np.float64)
        if matrix.shape[1] != len(char_list):
            raise SystemExit(
                f"char_list ({len(char_list)}) does not match the logits class axis "
                f"({matrix.shape[1]}); alignment indices would be wrong."
            )
        frame_ms = 1000.0 * duration / matrix.shape[0]

        greedy_ids = ctc_greedy_decode(logits.argmax(-1)[0].tolist(), blank)
        transcription = "".join(char_list[i] for i in greedy_ids)
        print(f"    model transcription: {transcription!r}")

        # prepare_tokenized_text wants an iterable of utterances whose tokens are
        # space-separated; a whole word passed as one token is not in char_list.
        tokenized, utt_begin = prepare_tokenized_text(config, [" ".join(sequence)])
        timings, char_probs, state_list = ctc_segmentation(config, matrix, tokenized)

        # `timings[i]` is already in SECONDS: the backtracker stores
        # (offsets[c] + t) * index_duration_in_seconds per ground-truth symbol.
        # A character owns the span up to the next symbol. The helper also inserts
        # a leading word break before the first real token.
        symbols = list(sequence)
        first = utt_begin[0] + 1  # skip the leading space inserted by the helper
        index_seconds = config.index_duration_in_seconds
        timed = []
        for offset, char in enumerate(symbols):
            if char == WORD_SEPARATOR:
                continue
            position = first + offset
            start = float(timings[position])
            end_frame = position + 1
            end = float(timings[end_frame]) if end_frame < len(timings) else duration
            if end <= start:
                continue
            lo = max(0, int(round(start / index_seconds)))
            hi = min(char_probs.shape[0], int(round(end / index_seconds)) + 1)
            # char_probs holds log-probabilities; exponentiate for a 0..1 score.
            window = np.clip(char_probs[lo:hi], -30.0, 0.0) if hi > lo else np.array([-30.0])
            timed.append({
                "char": char,
                "start": round(start, 4),
                "end": round(end, 4),
                "confidence": round(float(np.exp(window).mean()), 4),
            })
        if not timed:
            print("    ALIGNMENT FAILED: no timed characters")
            continue

        durations = [s["end"] - s["start"] for s in timed]
        uniform = float(np.mean(durations))
        distinct = sum(1 for d in durations if abs(d - uniform) > 0.02)
        mean_confidence = float(np.mean([s["confidence"] for s in timed]))
        print(
            f"    frames={matrix.shape[0]} (~{frame_ms:.1f}ms/frame) "
            f"infer={infer_seconds:.2f}s mean_conf={mean_confidence:.4f}"
        )
        print(
            f"    segments={len(timed)} audio={duration:.3f}s "
            f"first={timed[0]['start']:.3f}s last_end={timed[-1]['end']:.3f}s"
        )
        print(
            f"    durations min={min(durations):.3f} max={max(durations):.3f} "
            f"mean={uniform:.4f} stdev={float(np.std(durations)):.4f}"
        )
        print(
            f"    non-uniform: {distinct}/{len(durations)} "
            f"(equal-split text would give ~0)"
        )
        print(
            "    timeline: "
            + " ".join(f"{s['char']}[{s['start']:.2f}-{s['end']:.2f}]" for s in timed[:24])
        )

        results.append({
            "id": item["id"],
            "text": item["text"],
            "wav": item["wav"],
            "audio_duration": round(duration, 4),
            "model_transcription": transcription,
            "inference_seconds": round(infer_seconds, 3),
            "frame_ms": round(frame_ms, 4),
            "mean_confidence": round(mean_confidence, 4),
            "segments": timed,
        })

    out_path = os.path.join(PROBE_DIR, "ctc_probe_result.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump({"model": MODEL_ID, "blank": blank, "results": results},
                  handle, ensure_ascii=False, indent=2)
    print(f"\nwrote {out_path} ({len(results)}/{len(SENTENCES)} sentences aligned)")
    return 0 if len(results) == len(SENTENCES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
