#!/usr/bin/env python3
"""Stage 5.3 evidence collector.

Reads the real multi-format composition outputs produced by
``scripts/demo_stage_4_5.py`` and turns them into the measurements the report
claims: FFprobe geometry per format, black-band checks on frames taken from the
middle of every scene, and a side-by-side contact sheet of the same moment in all
three ratios.

Usage:
    PYTHONPATH=backend/src .venv/bin/python evidence/stage_5_3/collect_evidence.py
"""

from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))
sys.path.insert(0, HERE)

from measure import extract_frames, ffprobe_summary, measure_frame, write_json  # noqa: E402

PROJECT_DIR = os.path.join(REPO, "data", "studio_projects", "demo_stage_4_5")
SUMMARY_PATH = os.path.join(PROJECT_DIR, "demo_stage_4_5_summary.json")
OUT_DIR = os.path.join(HERE, "final")

# The composition engine removes the per-scene Blender directories once the edit is
# built, so the camera solve is captured by probe_formats.py instead and read back
# from there.
FRAMING_LABEL = os.environ.get("STAGE53_FRAMING_LABEL", "framing_v2")

# A frame is only useful as framing evidence if it is inside a scene, away from a
# crossfade blend and away from the closing fade-out to black.
SCENE_SAMPLE_FRACTION = 0.45


def scene_sample_times(manifest_path: str) -> list[tuple[str, float]]:
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    samples = []
    for entry in manifest["timeline"]["entries"]:
        span = entry["end_time"] - entry["start_time"]
        offset = span * SCENE_SAMPLE_FRACTION
        samples.append((entry["scene_id"], round(entry["start_time"] + offset, 3)))
    return samples


def load_framing_reports() -> dict:
    """Camera solves recorded by the Blender worker for the same cast and formats."""
    path = os.path.join(HERE, FRAMING_LABEL, "framing_report.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def contact_sheet(rows: list[list[str]], out_path: str, thumb_height: int = 480) -> None:
    """One row per sampled moment, one column per delivery format."""
    gap = 16
    label_height = 24

    thumbs: list[list[Image.Image]] = []
    for row in rows:
        items = []
        for path in row:
            with Image.open(path) as image:
                rgb = image.convert("RGB")
            scale = thumb_height / rgb.height
            items.append(rgb.resize((max(1, int(rgb.width * scale)), thumb_height)))
        thumbs.append(items)

    width = sum(thumbs[0][c].width for c in range(len(thumbs[0]))) + gap * (len(thumbs[0]) + 1)
    height = (thumb_height + label_height) * len(thumbs) + gap * (len(thumbs) + 1)
    sheet = Image.new("RGB", (width, height), (16, 16, 20))
    draw = ImageDraw.Draw(sheet)

    y = gap
    for index, items in enumerate(thumbs):
        x = gap
        for column, thumb in enumerate(items):
            if index == 0:
                draw.text((x, y), f"{thumb.width}x{thumb.height}", fill=(225, 225, 235))
            sheet.paste(thumb, (x, y + label_height))
            x += thumb.width + gap
        y += thumb_height + label_height

    sheet.save(out_path)


def main() -> None:
    if not os.path.isfile(SUMMARY_PATH):
        raise SystemExit(f"No demo summary at {SUMMARY_PATH}. Run scripts/demo_stage_4_5.py first.")

    with open(SUMMARY_PATH, encoding="utf-8") as handle:
        summary = json.load(handle)

    os.makedirs(OUT_DIR, exist_ok=True)
    framing_reports = load_framing_reports()
    formats = summary.get("outputs", {})
    evidence = {
        "stage": "5.3",
        "generated_at": summary.get("created_at"),
        "project_id": summary.get("project_id"),
        "voice_source": summary.get("voice_source"),
        "formats": {},
    }

    sheet_rows = []
    for video_format, record in formats.items():
        key = video_format.replace(":", "x")
        video_path = record["path"]
        job_id = record["job_id"]
        manifest_path = os.path.join(
            PROJECT_DIR, "compositions", job_id, "composition_manifest.json"
        )

        samples = scene_sample_times(manifest_path)
        frame_dir = os.path.join(OUT_DIR, key)
        produced = extract_frames(video_path, [t for _, t in samples], frame_dir)

        frames = []
        for (scene_id, timestamp), path in zip(samples, produced):
            renamed = os.path.join(frame_dir, f"{scene_id}_t{timestamp:06.3f}s.png")
            if os.path.exists(renamed):
                os.remove(renamed)
            os.replace(path, renamed)
            measurement = measure_frame(renamed)
            measurement["scene_id"] = scene_id
            measurement["timestamp_seconds"] = timestamp
            frames.append(measurement)

        evidence["formats"][video_format] = {
            "job_id": job_id,
            "video_file_path": video_path,
            "file_size_bytes": record["file_size_bytes"],
            "duration_seconds": record["duration_seconds"],
            "ffprobe": ffprobe_summary(video_path),
            "checks": record.get("checks"),
            "subtitle_file_path": record.get("subtitle_file_path"),
            "subtitle_cue_count": record.get("subtitle_cue_count"),
            "text_layer_count": record.get("text_layer_count"),
            "transition_count": record.get("transition_count"),
            "scene_count": record.get("scene_count"),
            "frames": frames,
            "camera_solve": framing_reports.get(key, {}),
        }

        sheet_rows.append({
            "video_format": video_format,
            "frames": [
                {"path": frame["path"], "scene_id": frame["scene_id"]} for frame in frames
            ],
        })

        print(f"\n== {video_format} ==")
        print(f"   {video_path}")
        print(
            f"   ffprobe {evidence['formats'][video_format]['ffprobe']['width']}x"
            f"{evidence['formats'][video_format]['ffprobe']['height']} "
            f"{evidence['formats'][video_format]['ffprobe']['codec_name']}"
            f"/{evidence['formats'][video_format]['ffprobe']['pix_fmt']} "
            f"{evidence['formats'][video_format]['ffprobe']['avg_frame_rate']} "
            f"{evidence['formats'][video_format]['ffprobe']['duration']}s "
            f"audio={evidence['formats'][video_format]['ffprobe']['audio_codec']}"
        )
        for frame in frames:
            print(
                f"   {frame['scene_id']} t={frame['timestamp_seconds']:.2f}s "
                f"bands T/B/L/R = "
                f"{frame['top_black_band_ratio']:.3f}/{frame['bottom_black_band_ratio']:.3f}"
                f"/{frame['left_black_band_ratio']:.3f}/{frame['right_black_band_ratio']:.3f} "
                f"black_px={frame['global_black_pixel_ratio']:.3f}"
            )

    # Re-order rows so every format contributes its first frame to row one, etc.
    if sheet_rows:
        ordered = [
            [row["frames"][index]["path"] for row in sheet_rows]
            for index in range(len(sheet_rows[0]["frames"]))
        ]
        contact_sheet(ordered, os.path.join(OUT_DIR, "contact_sheet.png"))

    write_json(os.path.join(OUT_DIR, "evidence.json"), evidence)

    worst = max(
        (frame["max_edge_black_band_ratio"], video_format, frame["scene_id"])
        for video_format, payload in evidence["formats"].items()
        for frame in payload["frames"]
    )
    print(f"\nWorst black edge band across all formats: {worst[0]:.3f} ({worst[1]} {worst[2]})")
    print(f"Wrote {os.path.join(OUT_DIR, 'evidence.json')}")


if __name__ == "__main__":
    main()
