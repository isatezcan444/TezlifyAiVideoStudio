#!/usr/bin/env python3
"""Stage 5.3 probe: render the same Ali + Ayşe two-shot at every delivery format.

Runs the real Blender worker through the production animation engine, keeps the
frame PNGs and measures how much of each frame is a black band. This isolates the
framing question from the FFmpeg edit, so a bad vertical frame is attributed to the
camera solve rather than to the composition step.

Usage:
    PYTHONPATH=backend/src .venv/bin/python evidence/stage_5_3/probe_formats.py [--label baseline]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))
sys.path.insert(0, HERE)

from measure import measure_frame, write_json  # noqa: E402
from tezlify_studio.domain.value_objects.scene_graph import (  # noqa: E402
    CharacterPlacement,
    CharacterStyle,
    SceneBackground,
    SceneCamera,
    SceneCharacter,
    SceneDialogue,
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (  # noqa: E402
    BlenderAnimationEngineImpl,
)

FORMATS = {
    "16x9": (1920, 1080, "16:9"),
    "9x16": (1080, 1920, "9:16"),
    "1x1": (1080, 1080, "1:1"),
}

TIMESTAMPS_S = [0.05, 0.55, 0.95]
FPS = 30
DURATION_S = 1.0


def read_framing(project_dir: str, project_id: str, job_id: str) -> dict:
    """The camera solve the Blender worker computed, straight from its result file."""
    result_path = os.path.join(project_dir, project_id, "renders", job_id, "render_result.json")
    if not os.path.isfile(result_path):
        return {}
    with open(result_path, encoding="utf-8") as handle:
        return json.load(handle).get("framing", {})


def build_graph(width: int, height: int, aspect: str, project_id: str) -> SceneGraph:
    characters = [
        SceneCharacter(
            id="char_ali",
            name="Ali",
            style=CharacterStyle(
                hair_color="#2C1810", skin_tone="#F5D0A9",
                shirt_color="#3B82F6", pants_color="#1E293B",
            ),
        ),
        SceneCharacter(
            id="char_ayse",
            name="Ayşe",
            style=CharacterStyle(
                hair_color="#4A2C1A", skin_tone="#F8D9BC",
                shirt_color="#EC4899", pants_color="#334155",
            ),
        ),
    ]
    return SceneGraph(
        project_id=project_id,
        title="Stage 5.3 framing probe",
        resolution=SceneResolution(width=width, height=height, aspect_ratio=aspect, fps=FPS),
        characters=characters,
        scenes=[
            StudioScene(
                scene_id="scene_01",
                duration_seconds=DURATION_S,
                background=SceneBackground(asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle="two_shot", fov=45.0, movement="static"),
                character_placements=[
                    CharacterPlacement(character_id="char_ali", position=[-0.55, 0.0, 0.0],
                                       rotation_y=12.0, pose="standing", expression="cheerful"),
                    CharacterPlacement(character_id="char_ayse", position=[0.55, 0.0, 0.0],
                                       rotation_y=-12.0, pose="standing", expression="cheerful"),
                ],
                dialogues=[
                    SceneDialogue(character_id="char_ali", start_time=0.1, end_time=0.5,
                                  text="Merhaba Ayşe, bugün nasılsın?"),
                    SceneDialogue(character_id="char_ayse", start_time=0.55, end_time=0.95,
                                  text="İyiyim Ali, teşekkür ederim."),
                ],
            )
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--only", default=None, help="single key such as 9x16")
    args = parser.parse_args()

    out_root = os.path.join(HERE, args.label)
    shutil.rmtree(out_root, ignore_errors=True)
    os.makedirs(out_root, exist_ok=True)

    engine = BlenderAnimationEngineImpl(
        base_projects_dir=os.path.join(REPO, "data", "studio_projects"),
        assets_dir=os.path.join(REPO, "data", "studio_assets"),
        keep_frames=True,
    )

    report = []
    for key, (width, height, aspect) in FORMATS.items():
        if args.only and args.only != key:
            continue
        project_id = f"stage53_probe_{args.label}"
        job_id = f"probe_{key}"
        graph = build_graph(width, height, aspect, project_id)
        print(f"== rendering {key} {width}x{height} ({aspect}) ==", flush=True)
        meta = engine.render_animation(
            scene_graph=graph,
            project_id=project_id,
            job_id=job_id,
            engine_override="BLENDER_WORKBENCH",
            include_audio=False,
        )
        frames_dir = os.path.join(
            REPO, "data", "studio_projects", project_id, "frames", job_id
        )
        samples = []
        for ts in TIMESTAMPS_S:
            frame_index = int(round(ts * FPS)) + 1
            src = os.path.join(frames_dir, f"frame_{frame_index:04d}.png")
            if not os.path.isfile(src):
                continue
            dst = os.path.join(out_root, f"{key}_t{ts:05.2f}s.png")
            shutil.copyfile(src, dst)
            measurement = measure_frame(dst)
            measurement["format"] = key
            measurement["timestamp_seconds"] = ts
            samples.append(measurement)
            print(
                f"   {key} t={ts:.2f}s black bands "
                f"top={measurement['top_black_band_ratio']:.3f} "
                f"bottom={measurement['bottom_black_band_ratio']:.3f} "
                f"left={measurement['left_black_band_ratio']:.3f} "
                f"right={measurement['right_black_band_ratio']:.3f} "
                f"black_px={measurement['global_black_pixel_ratio']:.3f} "
                f"content={measurement['content_box']['coverage_ratio']:.3f}",
                flush=True,
            )
        report.append({
            "format": key,
            "resolution": f"{width}x{height}",
            "video_file_path": meta.video_file_path,
            "frames_dir": frames_dir,
            "framing": read_framing(
                os.path.join(REPO, "data", "studio_projects"), project_id, job_id
            ),
            "samples": samples,
        })

    write_json(os.path.join(out_root, "probe_report.json"), report)
    write_json(
        os.path.join(out_root, "framing_report.json"),
        {entry["format"]: entry["framing"] for entry in report},
    )
    print(f"\nWrote {os.path.join(out_root, 'probe_report.json')}")


if __name__ == "__main__":
    main()
