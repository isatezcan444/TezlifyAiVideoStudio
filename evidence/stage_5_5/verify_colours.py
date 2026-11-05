#!/usr/bin/env python3
"""Stage 5.5 verification: do material colours survive into a real MP4?

Runs the production Blender engine twice over the same scene graph - once with
the new EEVEE default, once with Workbench - into an isolated DATA_DIR, then
measures the saturation of the decoded frames. Nothing is written inside the
repository's data/ tree.

Usage: DATA_DIR=/tmp/tezlify-55 python evidence/stage_5_5/verify_colours.py
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

from PIL import Image, ImageStat

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))

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
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (  # noqa: E402
    BlenderAnimationEngineImpl,
)

OUT = os.path.dirname(os.path.abspath(__file__))


def build_graph() -> SceneGraph:
    return SceneGraph(
        project_id="stage55_colours",
        title="Stage 5.5 Renk Doğrulaması",
        resolution=SceneResolution(width=1920, height=1080, aspect_ratio="16:9", fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_colour",
                duration_seconds=2.0,
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
                dialogues=[],
            )
        ],
    )


def frame_saturation(frames_dir: str) -> dict:
    """Mean HSV saturation over the sampled frames, in Pillow only (no numpy here)."""
    paths = sorted(glob.glob(os.path.join(frames_dir, "frame_*.png")))[:8]
    values = []
    for p in paths:
        with Image.open(p) as im:
            values.append(float(ImageStat.Stat(im.convert("HSV").split()[1]).mean[0]))
    mean = round(sum(values) / len(values), 2) if values else None
    return {"frames_sampled": len(paths), "mean_saturation": mean,
            "per_frame": [round(v, 2) for v in values]}


def main() -> None:
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir or data_dir == os.path.join(REPO, "data"):
        raise SystemExit("refusing to run without an isolated DATA_DIR")
    engine = BlenderAnimationEngineImpl(
        base_projects_dir=os.path.join(data_dir, "studio_projects"),
        assets_dir=os.path.join(REPO, "data", "studio_assets"),
        keep_frames=True,
    )
    results = {}
    for label, override in (("eevee", "BLENDER_EEVEE"), ("workbench", "BLENDER_WORKBENCH")):
        graph = build_graph()
        meta = engine.render_animation(
            scene_graph=graph, project_id=f"stage55_colours_{label}",
            job_id=f"colour_{label}", engine_override=override, include_audio=False,
        )
        frames_dir = os.path.join(data_dir, "studio_projects", f"stage55_colours_{label}",
                                  "frames", f"colour_{label}")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,codec_name,pix_fmt,avg_frame_rate", "-of", "json",
             meta.video_file_path],
            capture_output=True, text=True,
        )
        results[label] = {
            "engine_reported": meta.engine,
            "ffprobe": json.loads(probe.stdout).get("streams", [{}])[0],
            "video": meta.video_file_path,
            "colour": frame_saturation(frames_dir),
        }
        print(f"{label}: engine={meta.engine} saturation={results[label]['colour']['mean_saturation']}")

    with open(os.path.join(OUT, "colour_verification.json"), "w") as fh:
        json.dump(results, fh, indent=2)

    # Keep two frames as visual proof.
    for label in ("eevee", "workbench"):
        src = sorted(glob.glob(os.path.join(
            data_dir, "studio_projects", f"stage55_colours_{label}", "frames",
            f"colour_{label}", "frame_*.png")))[30]
        Image.open(src).save(os.path.join(OUT, f"colour_{label}_frame31.png"))
    print("wrote colour_verification.json + two frames")


if __name__ == "__main__":
    main()
