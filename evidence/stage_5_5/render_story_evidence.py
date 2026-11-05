#!/usr/bin/env python3
"""Stage 5.5 evidence: a three-scene story, rendered for real in three formats.

What this produces, all from the real pipeline:

  1. Turkish dialogue audio (macOS ``say`` / Yelda tr_TR) for six lines.
  2. Real local CTC forced alignment of that exact audio into visemes.
  3. Three real Blender renders (EEVEE) of the same story in 16:9, 9:16 and 1:1,
     each with the dialogue mixed into the MP4 by FFmpeg.
  4. Frame samples and contact sheets decoded from those MP4s.
  5. Measurements: saturation, audio loudness, decode integrity, framing.

Usage:
    PYTHONPATH=backend/src .venv/bin/python evidence/stage_5_5/render_story_evidence.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))

# Keep every artefact of this run inside the evidence folder: no user data dir.
os.environ.setdefault("DATA_DIR", os.path.join(HERE, ".data"))

from PIL import Image, ImageDraw  # noqa: E402

from tezlify_studio.application.services.lip_sync_resolver import LipSyncResolver  # noqa: E402
from tezlify_studio.domain.enums.studio_status import (  # noqa: E402
    CameraAngle,
    CameraMovement,
    CharacterExpression,
    CharacterPose,
)
from tezlify_studio.domain.value_objects.scene_graph import (  # noqa: E402
    CharacterPlacement,
    SceneBackground,
    SceneCamera,
    SceneCharacter,
    SceneDialogue,
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.infrastructure.alignment.ctc_forced_alignment_impl import (  # noqa: E402
    CTCForcedAlignmentImpl,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (  # noqa: E402
    BlenderAnimationEngineImpl,
)
from tezlify_studio.infrastructure.configuration.settings import settings  # noqa: E402

OUT = os.path.join(HERE, "story")
AUDIO_DIR = os.path.join(OUT, "audio")
RENDERS = os.path.join(OUT, "renders")
ASSETS = os.path.join(REPO, "data", "studio_assets")
PROJECT_ID = "stage55_story"

FORMATS = [
    ("16x9", 1280, 720, "16:9"),
    ("9x16", 720, 1280, "9:16"),
    ("1x1", 900, 900, "1:1"),
]

STORY = [
    {
        "scene_id": "scene_encounter",
        "angle": CameraAngle.TWO_SHOT,
        "movement": CameraMovement.SLOW_ZOOM_IN,
        "background": "bg_modern_cafe",
        "expressions": {"char_ali": CharacterExpression.CHEERFUL,
                        "char_ayse": CharacterExpression.CHEERFUL},
        "lines": [
            ("char_ali", "Merhaba Ayşe! Seni burada görmek ne güzel."),
            ("char_ayse", "Ali! Ben de tam seni düşünüyordum."),
        ],
    },
    {
        "scene_id": "scene_conversation",
        "angle": CameraAngle.MEDIUM_SHOT,
        "movement": CameraMovement.STATIC,
        "background": "bg_modern_cafe",
        "expressions": {"char_ali": CharacterExpression.CHEERFUL,
                        "char_ayse": CharacterExpression.CHEERFUL},
        "lines": [
            ("char_ayse", "Yeni animasyon projesi nasıl gidiyor?"),
            ("char_ali", "Harika gidiyor! Dün gece bütün sahneleri bitirdim."),
        ],
    },
    {
        "scene_id": "scene_reaction",
        "angle": CameraAngle.OVER_SHOULDER,
        "movement": CameraMovement.SLOW_ZOOM_IN,
        "background": "bg_modern_cafe",
        "expressions": {"char_ali": CharacterExpression.SAD,
                        "char_ayse": CharacterExpression.SURPRISED},
        "lines": [
            ("char_ali", "Ama sabah bilgisayar bir anda çöktü."),
            ("char_ayse", "Gerçekten mi? Çok üzüldüm, geçmiş olsun."),
        ],
    },
]

LEAD_IN = 0.5
GAP = 0.5       # silence between two lines so they never talk over each other
TAIL = 1.2      # room for the listening reaction and the settle before the cut


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def speak(text: str, stem: str) -> tuple[str, float]:
    """Real Turkish speech from the OS voice, converted to mp3."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    aiff = os.path.join(AUDIO_DIR, stem + ".aiff")
    mp3 = os.path.join(AUDIO_DIR, stem + ".mp3")
    if not os.path.exists(mp3):
        run(["say", "-v", "Yelda", "-r", "170", "-o", aiff, text])
        run(["ffmpeg", "-y", "-i", aiff, "-ac", "1", "-ar", "44100", "-b:a", "128k", mp3])
        os.remove(aiff)
    duration = float(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", mp3,
    ]).stdout.strip())
    return mp3, duration


def build_graph(resolution: SceneResolution) -> tuple[SceneGraph, list[dict]]:
    scenes, timeline = [], []
    for spec in STORY:
        dialogues = []
        cursor = LEAD_IN
        for index, (character_id, text) in enumerate(spec["lines"], start=1):
            stem = f"{spec['scene_id']}_{character_id}_{index}"
            audio, duration = speak(text, stem)
            start = round(cursor, 2)
            end = round(start + duration + 0.15, 2)
            dialogues.append(SceneDialogue(
                character_id=character_id, start_time=start, end_time=end,
                text=text, audio_file=audio,
            ))
            timeline.append({"scene_id": spec["scene_id"], "character_id": character_id,
                             "text": text, "audio_file": audio, "start": start,
                             "end": end, "audio_seconds": round(duration, 2)})
            cursor = end + GAP
        scene_duration = round(max(6.0, cursor - GAP + TAIL), 2)
        scenes.append(StudioScene(
            scene_id=spec["scene_id"],
            duration_seconds=scene_duration,
            background=SceneBackground(asset_id=spec["background"]),
            camera=SceneCamera(angle=spec["angle"], movement=spec["movement"]),
            character_placements=[
                CharacterPlacement(character_id="char_ali", position=[-0.55, 0.0, 0.0],
                                   rotation_y=14.0, pose=CharacterPose.STANDING,
                                   expression=spec["expressions"]["char_ali"]),
                CharacterPlacement(character_id="char_ayse", position=[0.55, 0.0, 0.0],
                                   rotation_y=-14.0, pose=CharacterPose.STANDING,
                                   expression=spec["expressions"]["char_ayse"]),
            ],
            dialogues=dialogues,
        ))
    return SceneGraph(
        project_id=PROJECT_ID,
        title="Kafede Karşılaşma",
        resolution=resolution,
        characters=[SceneCharacter(id="char_ali", name="Ali"),
                    SceneCharacter(id="char_ayse", name="Ayşe")],
        scenes=scenes,
    ), timeline


def ffprobe(path: str) -> dict:
    return json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path,
    ]).stdout)


def volume(path: str) -> dict:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                           "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True)
    out = {}
    for line in proc.stderr.splitlines():
        for key in ("mean_volume", "max_volume"):
            if f"{key}:" in line:
                out[key] = float(line.split(f"{key}:")[1].split("dB")[0].strip())
    return out


def mean_saturation(frame_path: str) -> float:
    with Image.open(frame_path) as im:
        hist = im.convert("HSV").split()[1].histogram()
    total = sum(hist)
    return sum(i * count for i, count in enumerate(hist)) / total / 255.0


def extract_frames(mp4: str, folder: str, count: int = 16) -> list[str]:
    os.makedirs(folder, exist_ok=True)
    duration = float(ffprobe(mp4)["format"]["duration"])
    frames = []
    for index in range(count):
        t = duration * (index + 0.5) / count
        path = os.path.join(folder, f"frame_{index:02d}_t{t:05.2f}.png")
        run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", path])
        if os.path.exists(path):
            frames.append(path)
    return frames


def contact_sheet(frames: list[str], path: str, columns: int = 4) -> str:
    thumbs = []
    for frame in frames:
        with Image.open(frame) as im:
            thumb = im.convert("RGB")
            thumb.thumbnail((480, 480))
            thumbs.append((thumb.copy(), os.path.basename(frame)))
    if not thumbs:
        raise RuntimeError("no frames to lay out")
    cell_w = max(t.width for t, _ in thumbs)
    cell_h = max(t.height for t, _ in thumbs) + 22
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), (24, 24, 30))
    draw = ImageDraw.Draw(sheet)
    for index, (thumb, label) in enumerate(thumbs):
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        sheet.paste(thumb, (x + (cell_w - thumb.width) // 2, y))
        draw.text((x + 6, y + cell_h - 18), label, fill=(235, 235, 235))
    sheet.save(path)
    return path


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)
    print("1. Real Turkish dialogue audio (macOS say / Yelda tr_TR)")

    provider = CTCForcedAlignmentImpl(
        python_executable=settings.alignment_python_executable,
        model_id=settings.alignment_model_id,
        cache_dir=settings.alignment_cache_dir,
        model_cache_dir=settings.alignment_model_cache_dir,
    )
    print(f"   alignment provider: {provider.describe()} available={provider.is_available()}")

    results = {"formats": [], "alignment": {}, "timeline": [], "started_at": time.time()}
    for name, width, height, aspect in FORMATS:
        print(f"\n2. {name} ({width}x{height}) — building graph and aligning")
        graph, timeline = build_graph(SceneResolution(
            width=width, height=height, aspect_ratio=aspect, fps=30))
        resolved, report = LipSyncResolver(provider).resolve(graph)
        print(f"   {json.dumps(report.to_dict(), ensure_ascii=False)}")
        results["alignment"][name] = report.to_dict()
        results["timeline"] = timeline
        if not report.uses_real_alignment:
            print("   ABORT: real alignment unavailable; refusing to claim lip sync")
            return 2

        job_id = f"story_{name}"
        started = time.time()
        engine = BlenderAnimationEngineImpl(
            base_projects_dir=os.path.join(RENDERS, name),
            assets_dir=ASSETS,
            keep_frames=True,
        )
        meta = engine.render_animation(
            scene_graph=resolved, project_id=PROJECT_ID, job_id=job_id,
            include_audio=True,
        )
        elapsed = round(time.time() - started, 1)
        mp4 = os.path.join(RENDERS, name, PROJECT_ID, "renders", job_id, f"{job_id}.mp4")
        assert os.path.exists(mp4), mp4
        probe = ffprobe(mp4)
        streams = {s["codec_type"]: s for s in probe["streams"]}
        frames = extract_frames(mp4, os.path.join(RENDERS, name, "frames"), 16)
        sheet = contact_sheet(frames, os.path.join(RENDERS, name, "contact_sheet.png"))
        result_path = os.path.join(RENDERS, name, PROJECT_ID, "renders", job_id,
                                   "render_result.json")
        result = json.load(open(result_path)) if os.path.exists(result_path) else {}
        level = volume(mp4)
        entry = {
            "format": name, "width": width, "height": height, "aspect": aspect,
            "mp4": mp4, "render_seconds": elapsed,
            "video_codec": streams.get("video", {}).get("codec_name"),
            "audio_codec": streams.get("audio", {}).get("codec_name"),
            "pix_fmt": streams.get("video", {}).get("pix_fmt"),
            "duration": float(probe["format"]["duration"]),
            "size_bytes": int(probe["format"]["size"]),
            "meta": meta.model_dump(mode="json"),
            "volume": level,
            "frames": frames,
            "frame_saturation": [round(mean_saturation(f), 4) for f in frames],
            "contact_sheet": sheet,
            "animation": result.get("animation", {}),
            "framing": result.get("framing", {}),
            "engine_config": result.get("engine_config", {}),
            "lip_sync": result.get("lip_sync", {}),
        }
        results["formats"].append(entry)
        print(f"   rendered in {elapsed}s -> {mp4}")
        print(f"   saturation mean {sum(entry['frame_saturation']) / len(entry['frame_saturation']):.3f}, "
              f"audio {entry['audio_codec']} {level}")

    results["finished_at"] = time.time()
    with open(os.path.join(OUT, "story_evidence.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    print(f"\nWrote {os.path.join(OUT, 'story_evidence.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
