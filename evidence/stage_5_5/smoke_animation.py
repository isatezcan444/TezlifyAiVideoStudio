#!/usr/bin/env python3
"""Stage 5.5 smoke render: does the animation plan actually move the rig?

Isolated DATA_DIR, short scene, production engine. Prints the worker's own
report so a failure is visible rather than inferred from a still frame.
"""
from __future__ import annotations

import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))

from tezlify_studio.domain.enums.studio_status import (  # noqa: E402
    CameraAngle, CameraMovement, CharacterExpression, CharacterPose,
)
from tezlify_studio.domain.value_objects.scene_graph import (  # noqa: E402
    CharacterPlacement, DialogueViseme, SceneBackground, SceneCamera, SceneCharacter,
    SceneGraph, SceneResolution, StudioScene, SceneDialogue,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (  # noqa: E402
    BlenderAnimationEngineImpl,
)

data_dir = os.environ.get("DATA_DIR")
assert data_dir and data_dir != os.path.join(REPO, "data"), "isolated DATA_DIR required"

visemes = [
    DialogueViseme(time=i * 0.22, end_time=i * 0.22 + 0.18, viseme=v, phoneme=p,
                   confidence=0.7, source="ctc_forced")
    for i, (v, p) in enumerate([("CLOSED", "m"), ("OPEN", "e"), ("DENTAL", "r"),
                                ("OPEN", "a"), ("SIBILANT", "h"), ("CLOSED", "b"),
                                ("OPEN", "a"), ("ROUND", "o"), ("CLOSED", "y")])
]

graph = SceneGraph(
    project_id="stage55_smoke",
    title="Stage 5.5 Animasyon Duman Testi",
    resolution=SceneResolution(width=1920, height=1080, aspect_ratio="16:9", fps=30),
    characters=[SceneCharacter(id="char_ali", name="Ali"),
                SceneCharacter(id="char_ayse", name="Ayşe")],
    scenes=[StudioScene(
        scene_id="scene_smoke",
        duration_seconds=4.0,
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
        dialogues=[SceneDialogue(character_id="char_ali", start_time=0.3, end_time=2.3,
                                 text="Merhaba Ayşe, bugün nasılsın?", visemes=visemes)],
    )],
)

engine = BlenderAnimationEngineImpl(
    base_projects_dir=os.path.join(data_dir, "studio_projects"),
    assets_dir=os.path.join(REPO, "data", "studio_assets"),
    keep_frames=True,
)


def progress(pct, step):
    if step and not step.startswith("Rendered frame"):
        print(f"   [{pct:5.1f}] {step}")


meta = engine.render_animation(scene_graph=graph, project_id="stage55_smoke",
                               job_id="smoke1", progress_callback=progress,
                               include_audio=False)
print("VIDEO", meta.video_file_path, "engine", meta.engine)

import json  # noqa: E402
result = json.load(open(os.path.join(data_dir, "studio_projects", "stage55_smoke",
                                     "renders", "smoke1", "render_result.json")))
print("keys:", sorted(result))
for key in ("animation", "lip_sync", "engine_config"):
    if key in result:
        print(f"--- {key}: {json.dumps(result[key], ensure_ascii=False)[:900]}")
