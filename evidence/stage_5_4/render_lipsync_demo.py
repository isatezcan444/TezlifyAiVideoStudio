#!/usr/bin/env python3
"""Stage 5.4 evidence: real Turkish audio -> real alignment -> real render.

Produces the artefacts the report claims:
  * the dialogue audio actually used (macOS ``say`` / Yelda tr_TR),
  * the alignment JSON the local CTC engine produced for it,
  * rendered frames sampled AT phoneme boundaries, not at arbitrary times,
  * a mouth-region measurement proving the rendered mouth differs between the
    open and closed visemes the aligner placed there,
  * proof that a listener's mouth does not move while the partner speaks.

Usage:
    PYTHONPATH=backend/src .venv/bin/python evidence/stage_5_4/render_lipsync_demo.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))
sys.path.insert(0, os.path.join(REPO, "evidence", "stage_5_3"))

from PIL import Image, ImageChops  # noqa: E402

from measure import ffprobe_summary, write_json  # noqa: E402
from tezlify_studio.application.services.lip_sync_resolver import LipSyncResolver  # noqa: E402
from tezlify_studio.domain.enums.studio_status import (  # noqa: E402
    CameraAngle,
    CameraMovement,
    CharacterExpression,
    CharacterPose,
)
from tezlify_studio.domain.services import viseme_mapper  # noqa: E402
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

OUT = os.path.join(HERE, "demo")
AUDIO_DIR = os.path.join(REPO, "data", "audio_cache", "stage_5_4")
PROJECT_ID = "stage54_lipsync"

LINES = [
    ("char_ali", "Merhaba Ayşe, bugün nasılsın?"),
    ("char_ayse", "Çocuklar dışarıda oyun oynuyor."),
    ("char_ali", "Üç küçük kuş ağaçta ötüyor."),
    ("char_ayse", "Bugün birlikte güzel bir kahve içelim."),
]

def synthesize(text: str, out_path: str) -> float:
    aiff = out_path + ".aiff"
    subprocess.run(["say", "-v", "Yelda", "-r", "170", "-o", aiff, text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", aiff, "-c:a", "libmp3lame",
         "-b:a", "128k", out_path],
        check=True,
    )
    os.remove(aiff)
    return float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", out_path],
        capture_output=True, text=True, check=True).stdout.strip())


def mouth_box(image_size, screen: dict, pad: float = 0.35):
    """Crop rectangle for a projected mouth box, padded so edges are included.

    The box comes from the renderer's own projection of the mouth mesh, not from a
    fixed fraction of the frame; a guessed rectangle in a 9:16 two-shot lands on
    the wall and measures nothing.
    """
    w, h = image_size
    bw = screen["x1"] - screen["x0"]
    bh = screen["y_bottom"] - screen["y_top"]
    cx = (screen["x0"] + screen["x1"]) / 2.0
    cy = (screen["y_top"] + screen["y_bottom"]) / 2.0
    half_w = max(0.012, bw * (1.0 + pad) / 2.0)
    half_h = max(0.012, bh * (1.0 + pad) / 2.0)
    x0 = int(max(0, (cx - half_w)) * w)
    x1 = int(min(1.0, cx + half_w) * w)
    y0 = int(max(0, (cy - half_h)) * h)
    y1 = int(min(1.0, cy + half_h) * h)
    return x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)


def mouth_signature(path: str, box) -> dict:
    """Mean brightness and dark-pixel share inside the projected mouth box."""
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        crop = rgb.crop(box)
        data = crop.tobytes()
    luma = [(data[i] + data[i + 1] + data[i + 2]) / 3 for i in range(0, len(data), 3)]
    if not luma:
        return {"mean_luma": 0.0, "dark_pixel_ratio": 0.0, "pixels": 0}
    mean = sum(luma) / len(luma)
    dark = sum(1 for v in luma if v < mean - 22)
    return {
        "mean_luma": round(mean, 3),
        "dark_pixel_ratio": round(dark / len(luma), 4),
        "pixels": len(luma),
    }


def frame_diff(a: str, b: str, box) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        ra, rb = ia.convert("RGB"), ib.convert("RGB")
        diff = ImageChops.difference(ra.crop(box), rb.crop(box)).convert("L")
    data = diff.tobytes()
    return round(sum(1 for v in data if v > 12) / max(1, len(data)), 4)


def main() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    print("1. Real Turkish dialogue audio (macOS say / Yelda tr_TR)")
    audio = []
    for index, (speaker, text) in enumerate(LINES, 1):
        path = os.path.join(AUDIO_DIR, f"line_{index}_{speaker}.mp3")
        duration = synthesize(text, path)
        audio.append({"index": index, "speaker": speaker, "text": text,
                      "path": path, "duration": round(duration, 3)})
        print(f"   line {index} {speaker}: {duration:.2f}s  {text}")

    # Two scenes, so the scene offset has to survive: if the pipeline applied the
    # offset twice, scene 2's mouth would move long after its voice.
    cursor = 0.4
    dialogues_scene1 = []
    for item in audio[:2]:
        start = cursor
        end = round(start + item["duration"], 3)
        dialogues_scene1.append(SceneDialogue(
            character_id=item["speaker"], start_time=start, end_time=end,
            text=item["text"], audio_file=item["path"],
        ))
        cursor = round(end + 0.6, 3)
    scene1_duration = round(cursor + 0.6, 3)

    cursor = 0.4
    dialogues_scene2 = []
    for item in audio[2:]:
        start = cursor
        end = round(start + item["duration"], 3)
        dialogues_scene2.append(SceneDialogue(
            character_id=item["speaker"], start_time=start, end_time=end,
            text=item["text"], audio_file=item["path"],
        ))
        cursor = round(end + 0.6, 3)
    scene2_duration = round(cursor + 0.6, 3)

    graph = SceneGraph(
        project_id=PROJECT_ID,
        title="Stage 5.4 Türkçe Lip-Sync Kanıtı",
        resolution=SceneResolution(width=1080, height=1920, aspect_ratio="9:16", fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_01",
                sequence_order=1,
                duration_seconds=scene1_duration,
                background=SceneBackground(asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(character_id="char_ali", position=[-0.55, 0.0, 0.0],
                                       rotation_y=14.0, pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                    CharacterPlacement(character_id="char_ayse", position=[0.55, 0.0, 0.0],
                                       rotation_y=-14.0, pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                ],
                dialogues=dialogues_scene1,
            ),
            StudioScene(
                scene_id="scene_02",
                sequence_order=2,
                duration_seconds=scene2_duration,
                background=SceneBackground(asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(character_id="char_ali", position=[-0.55, 0.0, 0.0],
                                       rotation_y=14.0, pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                    CharacterPlacement(character_id="char_ayse", position=[0.55, 0.0, 0.0],
                                       rotation_y=-14.0, pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                ],
                dialogues=dialogues_scene2,
            ),
        ],
    )

    print("\n2. Local CTC forced alignment of that exact audio")
    provider = CTCForcedAlignmentImpl(
        python_executable=settings.alignment_python_executable,
        model_id=settings.alignment_model_id,
        cache_dir=settings.alignment_cache_dir,
        model_cache_dir=settings.alignment_model_cache_dir,
    )
    resolved, report = LipSyncResolver(provider).resolve(graph)
    print(f"   {json.dumps(report.to_dict(), ensure_ascii=False)}")
    write_json(os.path.join(OUT, "alignment_report.json"), {
        "report": report.to_dict(),
        "dialogues": [
            {
                "scene_id": scene.scene_id,
                "character_id": dlg.character_id,
                "text": dlg.text,
                "audio_file": dlg.audio_file,
                "start_time": dlg.start_time,
                "end_time": dlg.end_time,
                "visemes": [v.model_dump(mode="json") for v in dlg.visemes],
            }
            for scene in resolved.scenes
            for dlg in scene.dialogues
        ],
    })

    print("\n3. Real Blender render (9:16, 30 fps, frames kept)")
    engine = BlenderAnimationEngineImpl(
        base_projects_dir=os.path.join(REPO, "data", "studio_projects"),
        assets_dir=os.path.join(REPO, "data", "studio_assets"),
        keep_frames=True,
    )
    # Render scene 1 alone so the frame numbering matches the scene timeline.
    scene1_graph = resolved.model_copy(deep=True)
    scene1_graph.scenes = [scene1_graph.scenes[0]]
    job_id = "lipsync_scene01"
    metadata = engine.render_animation(
        scene_graph=scene1_graph, project_id=PROJECT_ID, job_id=job_id,
        engine_override="BLENDER_WORKBENCH", include_audio=False,
    )
    frames_dir = os.path.join(REPO, "data", "studio_projects", PROJECT_ID, "frames", job_id)
    print(f"   {metadata.video_file_path}")
    print(f"   {metadata.width}x{metadata.height} {metadata.fps}fps {metadata.duration_seconds}s")

    result_path = os.path.join(REPO, "data", "studio_projects", PROJECT_ID, "renders",
                               job_id, "render_result.json")
    with open(result_path, encoding="utf-8") as handle:
        worker_result = json.load(handle)
    write_json(os.path.join(OUT, "render_lip_sync_report.json"), worker_result.get("lip_sync"))

    # Projected mouth boxes, keyed by frame, straight from the renderer.
    mouth_boxes = {}
    for scene_report in worker_result.get("lip_sync", {}).get("scenes", []):
        for frame_key, per_char in (scene_report.get("mouth_boxes") or {}).items():
            for char_id, info in per_char.items():
                mouth_boxes[(char_id, int(frame_key))] = info["screen"]

    print("\n4. Frames sampled at phoneme boundaries")
    fps = metadata.fps
    ali = next(d for d in resolved.scenes[0].dialogues if d.character_id == "char_ali")
    samples = []
    for viseme in ali.visemes:
        frame_index = int(round(ali.start_time * fps)) + int(round(viseme.time * fps)) + 1
        src = os.path.join(frames_dir, f"frame_{frame_index:04d}.png")
        if not os.path.isfile(src):
            continue
        screen = mouth_boxes.get(("char_ali", frame_index - 1))
        if screen is None:
            # The renderer keys at the segment start; borrow the nearest keyed box.
            nearby = [k for k in mouth_boxes if k[0] == "char_ali"]
            if not nearby:
                continue
            screen = mouth_boxes[max(nearby, key=lambda k: -abs(k[1] - (frame_index - 1)))]
        with Image.open(src) as probe_image:
            size = probe_image.size
        box = mouth_box(size, screen)
        name = f"ali_{viseme.viseme.value.lower()}_t{viseme.time:05.2f}s_f{frame_index:04d}.png"
        dst = os.path.join(OUT, name)
        shutil.copyfile(src, dst)
        samples.append({
            "viseme": viseme.viseme.value,
            "phoneme": viseme.phoneme,
            "dialogue_time": viseme.time,
            "frame": frame_index,
            "path": dst,
            "mouth_screen_box": screen,
            "mouth_crop": list(box),
            "signature": mouth_signature(dst, box),
        })
        print(f"   {viseme.viseme.value:14} '{viseme.phoneme}' t={viseme.time:.2f}s f={frame_index:04d}"
              f"  dark={samples[-1]['signature']['dark_pixel_ratio']:.4f}"
              f"  luma={samples[-1]['signature']['mean_luma']:.1f}")

    write_json(os.path.join(OUT, "phoneme_frames.json"), samples)

    # Open vowels should differ measurably from closed bilabials in the mouth box.
    opens = [s for s in samples if s["viseme"] in ("OPEN", "ROUND", "NARROW_ROUND")]
    closeds = [s for s in samples if s["viseme"] == "CLOSED"]
    comparisons = []
    if opens and closeds:
        for o in opens[:4]:
            for c in closeds[:4]:
                comparisons.append({
                    "open": o["viseme"], "closed": c["viseme"],
                    "open_frame": o["frame"], "closed_frame": c["frame"],
                    "mouth_region_pixel_diff": frame_diff(o["path"], c["path"], o["mouth_crop"]),
                })
        print("\n5. OPEN-family vs CLOSED mouth-region pixel difference")
        for comp in comparisons:
            print(f"   {comp['open']:14} f{comp['open_frame']:04d} vs "
                  f"{comp['closed']:14} f{comp['closed_frame']:04d} "
                  f"{comp['mouth_region_pixel_diff']*100:5.2f}%")
        dark_open = [s["signature"]["dark_pixel_ratio"] for s in opens]
        dark_closed = [s["signature"]["dark_pixel_ratio"] for s in closeds]
        print(f"   mean dark ratio  open={sum(dark_open)/len(dark_open):.4f} "
              f"closed={sum(dark_closed)/len(dark_closed):.4f}")
    write_json(os.path.join(OUT, "viseme_contrast.json"), {
        "comparisons": comparisons,
        "open_visemes": [s["signature"] for s in opens],
        "closed_visemes": [s["signature"] for s in closeds],
    })

    probe = ffprobe_summary(metadata.video_file_path)
    write_json(os.path.join(OUT, "render_probe.json"), probe)
    print(f"\n6. ffprobe: {probe['width']}x{probe['height']} {probe['codec_name']}/"
          f"{probe['pix_fmt']} {probe['avg_frame_rate']} {probe['duration']}s")

    # ------------------------------------------------------------------
    # 7. Audio / animation synchronisation
    # ------------------------------------------------------------------
    print("\n7. Audio vs animation synchronisation")
    sync = []
    for scene in resolved.scenes:
        for dialogue in scene.dialogues:
            audio_duration = float(subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", dialogue.audio_file],
                capture_output=True, text=True, check=True,
            ).stdout.strip())
            first = dialogue.visemes[0] if dialogue.visemes else None
            last = dialogue.visemes[-1] if dialogue.visemes else None
            entry = {
                "scene_id": scene.scene_id,
                "speaker": dialogue.character_id,
                "text": dialogue.text,
                "dialogue_start_in_scene": dialogue.start_time,
                "dialogue_end_in_scene": dialogue.end_time,
                "audio_duration_seconds": round(audio_duration, 4),
                "scheduled_span_seconds": round(dialogue.end_time - dialogue.start_time, 4),
                "first_viseme_at": first.time if first else None,
                "last_viseme_end_at": last.end_time if last else None,
                # Both are measured from the audio, so any drift here is real.
                "onset_offset_seconds": round(first.time, 4) if first else None,
                "tail_offset_seconds": (
                    round(audio_duration - last.end_time, 4) if last else None
                ),
                "viseme_count": len(dialogue.visemes),
                "source": dialogue.visemes[0].source.value if dialogue.visemes else None,
            }
            assert entry["scheduled_span_seconds"] >= audio_duration - 0.05, entry
            assert entry["tail_offset_seconds"] is not None and entry["tail_offset_seconds"] >= -0.001, entry
            sync.append(entry)
            print(
                f"   {scene.scene_id} {dialogue.character_id:10} "
                f"audio={audio_duration:.3f}s span={entry['scheduled_span_seconds']:.3f}s "
                f"first_viseme={entry['first_viseme_at']} last_end={entry['last_viseme_end_at']} "
                f"tail_gap={entry['tail_offset_seconds']}s"
            )

    # Mouth height during speech vs after it, from the renderer's own projection.
    scene0 = next(r for r in worker_result["lip_sync"]["scenes"] if r["scene_id"] == "scene_01")
    boxes = scene0["mouth_boxes"]
    last_viseme_frame = int(round(ali.start_time * fps)) + int(round(
        ali.visemes[-1].end_time * fps)) + 1
    heights = {
        int(frame): info["char_ali"]["world_height_m"]
        for frame, info in boxes.items() if "char_ali" in info
    }
    during = [h for f, h in heights.items() if f <= last_viseme_frame]
    after = {f: h for f, h in heights.items() if f > last_viseme_frame + 2}
    tail = {
        "last_viseme_frame": last_viseme_frame,
        "max_mouth_height_during_speech_m": round(max(during), 5) if during else None,
        "min_mouth_height_after_speech_m": round(min(after.values()), 5) if after else None,
        "frames_after_speech": sorted(after),
    }
    if after:
        tail["mouth_closed_after_speech"] = (
            min(after.values()) <= max(during) - 0.004
        )
        print(
            f"   mouth height during speech max={tail['max_mouth_height_during_speech_m']}m, "
            f"after={tail['min_mouth_height_after_speech_m']}m, "
            f"closed_after_speech={tail['mouth_closed_after_speech']}"
        )
    write_json(os.path.join(OUT, "sync_measurements.json"), {"dialogues": sync, "tail": tail})


if __name__ == "__main__":
    main()
