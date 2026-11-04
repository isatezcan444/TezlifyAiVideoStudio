import json
import os
import shutil
import tempfile

import pytest
from PIL import Image

from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import BlenderAnimationEngineImpl
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    StudioScene,
    SceneCharacter,
    CharacterPlacement,
    SceneDialogue,
    SceneResolution,
    SceneBackground,
    SceneCamera,
    CharacterPose,
    CharacterExpression,
)
from tezlify_studio.domain.enums.studio_status import (
    CameraAngle,
    CameraMovement,
)

def test_real_blender_animation_and_mp4_render():
    """Real end-to-end integration test executing Blender 5.2.3 in headless mode,

    animating Ali and Ayşe in a cafe, encoding to MP4 with FFmpeg, and validating
    technical parameters via FFprobe.
    """
    temp_dir = tempfile.mkdtemp(prefix="studio_render_test_")
    try:
        project_id = "test_cafe_project"
        job_id = "job_cafe_render_test"

        engine = BlenderAnimationEngineImpl(
            base_projects_dir=temp_dir,
            assets_dir=os.path.abspath("data/studio_assets"),
            keep_frames=False,
        )

        # 2-second SceneGraph with Ali & Ayşe in Modern Cafe
        scene_graph = SceneGraph(
            schema_version="1.0",
            project_id=project_id,
            title="Ali ve Ayşe Kafe Sohbeti Testi",
            description="Gerçek Blender headless animasyon entegrasyon testi",
            resolution=SceneResolution(width=1920, height=1080, fps=30),
            characters=[
                SceneCharacter(id="char_ali", name="Ali"),
                SceneCharacter(id="char_ayse", name="Ayşe"),
            ],
            scenes=[
                StudioScene(
                    scene_id="scene_cafe_01",
                    duration_seconds=2.0,
                    background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                    camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.SLOW_PAN_RIGHT),
                    character_placements=[
                        CharacterPlacement(
                            character_id="char_ali",
                            position=[-0.7, 0.0, 0.0],
                            rotation_y=35.0,
                            pose=CharacterPose.STANDING,
                            expression=CharacterExpression.CHEERFUL,
                        ),
                        CharacterPlacement(
                            character_id="char_ayse",
                            position=[0.7, 0.0, 0.0],
                            rotation_y=-35.0,
                            pose=CharacterPose.STANDING,
                            expression=CharacterExpression.NEUTRAL,
                        ),
                    ],
                    dialogues=[
                        SceneDialogue(
                            character_id="char_ali",
                            start_time=0.4,
                            end_time=1.6,
                            text="Merhaba Ayşe, kahveler hazır!",
                        )
                    ],
                )
            ],
        )

        progress_records = []
        def on_progress(pct: float, step: str):
            progress_records.append((pct, step))

        metadata = engine.render_animation(
            scene_graph=scene_graph,
            project_id=project_id,
            job_id=job_id,
            progress_callback=on_progress,
            engine_override="BLENDER_WORKBENCH",
        )

        # 1. Output file validation
        assert os.path.exists(metadata.video_file_path)
        assert os.path.isfile(metadata.video_file_path)
        assert metadata.file_size_bytes > 0
        assert os.path.getsize(metadata.video_file_path) == metadata.file_size_bytes

        # 2. Technical parameter validation
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.fps == 30
        assert metadata.video_codec == "h264"
        assert metadata.pixel_format == "yuv420p"
        assert metadata.container == "mp4"
        assert metadata.frame_count == 60  # 2.0s * 30fps
        assert metadata.duration_seconds >= 1.8  # ~2.0s
        assert metadata.render_duration_seconds > 0.0

        # 3. Verify populated Blender scene file was saved
        scene_path = os.path.join(temp_dir, project_id, "scenes", f"scene_{job_id}.blend")
        assert os.path.exists(scene_path)
        assert os.path.getsize(scene_path) > 0

        # 4. Verify progress callbacks were invoked
        assert len(progress_records) > 0
        final_pcts = [p[0] for p in progress_records]
        assert max(final_pcts) == 100.0

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ----------------------------------------------------------------------
# Stage 5.3 — real vertical composition, measured on real rendered pixels
# ----------------------------------------------------------------------

def _edge_black_band_ratios(path: str) -> dict:
    """Share of the frame taken by a fully black band touching each edge.

    A portrait frame that was really just a landscape frame with room added above
    and below shows up here as black world background, which is the failure this
    stage exists to remove.
    """
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        data = rgb.tobytes()
    stride = width * 3

    def row_black(y: int) -> bool:
        offset = y * stride
        return max(data[offset:offset + stride]) < 14

    def col_black(x: int) -> bool:
        offset = x * 3
        return max(
            max(data[offset::stride]),
            max(data[offset + 1::stride]),
            max(data[offset + 2::stride]),
        ) < 14

    def run(start: int, stop: int, step: int, length: int, is_black) -> float:
        count = 0
        index = start
        while (step > 0 and index < stop) or (step < 0 and index > stop):
            if not is_black(index):
                break
            count += 1
            index += step
        return count / length

    return {
        "top": run(0, height, 1, height, row_black),
        "bottom": run(height - 1, -1, -1, height, row_black),
        "left": run(0, width, 1, width, col_black),
        "right": run(width - 1, -1, -1, width, col_black),
    }


def _vertical_render_graph(resolution: SceneResolution) -> SceneGraph:
    return SceneGraph(
        schema_version="1.0",
        project_id="test_portrait_project",
        title="Ali ve Ayşe Dikey Kadraj Testi",
        resolution=resolution,
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_portrait_01",
                duration_seconds=1.0,
                background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ali",
                        position=[-0.55, 0.0, 0.0],
                        rotation_y=12.0,
                        pose=CharacterPose.STANDING,
                        expression=CharacterExpression.CHEERFUL,
                    ),
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.55, 0.0, 0.0],
                        rotation_y=-12.0,
                        pose=CharacterPose.STANDING,
                        expression=CharacterExpression.CHEERFUL,
                    ),
                ],
                dialogues=[
                    SceneDialogue(
                        character_id="char_ali",
                        start_time=0.1,
                        end_time=0.5,
                        text="Merhaba Ayşe, bugün nasılsın?",
                    ),
                    SceneDialogue(
                        character_id="char_ayse",
                        start_time=0.55,
                        end_time=0.95,
                        text="İyiyim Ali, teşekkür ederim.",
                    ),
                ],
            )
        ],
    )


@pytest.mark.parametrize(
    "width,height,aspect,profile_key",
    [
        (1920, 1080, "16:9", "landscape"),
        (1080, 1920, "9:16", "portrait"),
        (1080, 1080, "1:1", "square"),
    ],
)
def test_real_blender_render_frames_the_cast_for_every_delivery_format(
    width, height, aspect, profile_key
):
    """Renders Ali and Ayşe for real in each format and measures the result.

    Two independent proofs, because a 1080x1920 file on its own proves nothing:
    the pixels must carry no black letterbox band, and the camera solve must place
    every character's head and body inside that format's safe area.
    """
    temp_dir = tempfile.mkdtemp(prefix="studio_framing_test_")
    try:
        project_id = "test_portrait_project"
        job_id = f"job_framing_{aspect.replace(':', 'x')}"

        engine = BlenderAnimationEngineImpl(
            base_projects_dir=temp_dir,
            assets_dir=os.path.abspath("data/studio_assets"),
            keep_frames=True,
        )

        graph = _vertical_render_graph(
            SceneResolution(width=width, height=height, aspect_ratio=aspect, fps=30)
        )
        metadata = engine.render_animation(
            scene_graph=graph,
            project_id=project_id,
            job_id=job_id,
            engine_override="BLENDER_WORKBENCH",
            include_audio=False,
        )

        assert (metadata.width, metadata.height) == (width, height)
        assert metadata.pixel_format == "yuv420p"
        assert metadata.video_codec == "h264"

        result_path = os.path.join(temp_dir, project_id, "renders", job_id, "render_result.json")
        with open(result_path, encoding="utf-8") as handle:
            worker_result = json.load(handle)

        framing = worker_result["framing"]
        assert framing["profile"] == profile_key
        assert framing["aspect_ratio"] == aspect

        scene_report = framing["scenes"][0]
        assert scene_report["solve"]["fits_safe_area"] is True, (
            f"{aspect} could not frame the cast inside its safe area: {scene_report['solve']}"
        )
        assert scene_report["cast"] == ["char_ali", "char_ayse"]

        safe = framing["safe_area"]
        for char_id, box in scene_report["screen_boxes"].items():
            assert box["x0"] >= 0.0, f"{char_id} is cut off on the left in {aspect}"
            assert box["x1"] <= 1.0, f"{char_id} is cut off on the right in {aspect}"
            assert box["y_top"] >= 0.0, f"{char_id}'s head is cut off in {aspect}"
            assert box["y_bottom"] <= 1.0, f"{char_id}'s body is cut off in {aspect}"
            # The head must sit below the top safe inset, not under the platform UI.
            assert box["y_top"] >= safe["top"] - 0.05, (
                f"{char_id}'s head at {box['y_top']:.3f} is inside the {aspect} top safe band"
            )

        if aspect == "9:16":
            # The whole point of the stage: a portrait shot must use the frame.
            fill = scene_report["solve"]["fill_height"]
            assert fill > 0.6, f"portrait cast fills only {fill:.2f} of the safe band"
            assert scene_report["solve"]["distance_m"] < 3.0, (
                "portrait camera did not push in; the cast would be floating in wall"
            )

        frames_dir = os.path.join(temp_dir, project_id, "frames", job_id)
        for frame_name in ("frame_0001.png", "frame_0016.png", "frame_0030.png"):
            frame_path = os.path.join(frames_dir, frame_name)
            assert os.path.isfile(frame_path), f"missing rendered frame {frame_name}"
            bands = _edge_black_band_ratios(frame_path)
            assert bands["top"] == 0.0, f"{aspect} {frame_name} has a top black band: {bands}"
            assert bands["bottom"] == 0.0, f"{aspect} {frame_name} has a bottom black band: {bands}"
            assert bands["left"] == 0.0, f"{aspect} {frame_name} has a left black band: {bands}"
            assert bands["right"] == 0.0, f"{aspect} {frame_name} has a right black band: {bands}"

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.parametrize(
    "label,placements,camera_angle,expected_placed",
    [
        (
            "single_speaker",
            [
                CharacterPlacement(
                    character_id="char_ali",
                    position=[-0.4, 0.0, 0.0],
                    rotation_y=10.0,
                    pose=CharacterPose.STANDING,
                    expression=CharacterExpression.CHEERFUL,
                )
            ],
            CameraAngle.MEDIUM_SHOT,
            ["char_ali"],
        ),
        (
            "sitting_at_table",
            [
                CharacterPlacement(
                    character_id="char_ali",
                    position=[-0.45, -0.35, 0.0],
                    rotation_y=18.0,
                    pose=CharacterPose.SITTING,
                    expression=CharacterExpression.CHEERFUL,
                ),
                CharacterPlacement(
                    character_id="char_ayse",
                    position=[0.45, -0.35, 0.0],
                    rotation_y=-18.0,
                    pose=CharacterPose.SITTING,
                    expression=CharacterExpression.NEUTRAL,
                ),
            ],
            CameraAngle.TWO_SHOT,
            ["char_ali", "char_ayse"],
        ),
        (
            "widely_separated_cast",
            [
                CharacterPlacement(
                    character_id="char_ali",
                    position=[-1.15, 0.0, 0.0],
                    rotation_y=25.0,
                    pose=CharacterPose.STANDING,
                    expression=CharacterExpression.THINKING,
                ),
                CharacterPlacement(
                    character_id="char_ayse",
                    position=[1.15, 0.0, 0.0],
                    rotation_y=-25.0,
                    pose=CharacterPose.STANDING,
                    expression=CharacterExpression.SURPRISED,
                ),
            ],
            CameraAngle.WIDE_SHOT,
            ["char_ali", "char_ayse"],
        ),
    ],
)
def test_portrait_camera_reframes_for_different_character_positions(
    label, placements, camera_angle, expected_placed
):
    """Blocking is not a fixed camera: every layout must survive the 9:16 solve.

    A single speaker, a seated pair and a cast standing far apart have completely
    different silhouettes. Each one has to land inside the portrait safe area with
    its head uncut, which is what a static per-angle camera could not guarantee.
    """
    temp_dir = tempfile.mkdtemp(prefix="studio_framing_layout_")
    try:
        project_id = "test_layout_project"
        job_id = f"job_layout_{label}"

        engine = BlenderAnimationEngineImpl(
            base_projects_dir=temp_dir,
            assets_dir=os.path.abspath("data/studio_assets"),
            keep_frames=False,
        )

        graph = SceneGraph(
            schema_version="1.0",
            project_id=project_id,
            title=f"Dikey kadraj yerleşim testi: {label}",
            resolution=SceneResolution(width=1080, height=1920, aspect_ratio="9:16", fps=30),
            characters=[
                SceneCharacter(id="char_ali", name="Ali"),
                SceneCharacter(id="char_ayse", name="Ayşe"),
            ],
            scenes=[
                StudioScene(
                    scene_id="scene_layout",
                    duration_seconds=1.0,
                    background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                    camera=SceneCamera(angle=camera_angle, movement=CameraMovement.STATIC),
                    character_placements=placements,
                    dialogues=[
                        SceneDialogue(
                            character_id="char_ali",
                            start_time=0.1,
                            end_time=0.6,
                            text="Merhaba, bugün nasılsın?",
                        )
                    ],
                )
            ],
        )

        engine.render_animation(
            scene_graph=graph,
            project_id=project_id,
            job_id=job_id,
            engine_override="BLENDER_WORKBENCH",
            include_audio=False,
        )

        result_path = os.path.join(
            temp_dir, project_id, "renders", job_id, "render_result.json"
        )
        with open(result_path, encoding="utf-8") as handle:
            framing = json.load(handle)["framing"]

        assert framing["profile"] == "portrait"
        scene_report = framing["scenes"][0]
        assert scene_report["placed"] == expected_placed
        # Every rig imported into the shot is framed, not only the ones this scene
        # re-placed: an idle cast member is still standing on the stage set.
        assert set(expected_placed) <= set(scene_report["cast"])
        assert scene_report["solve"]["fits_safe_area"] is True, scene_report["solve"]

        safe = framing["safe_area"]
        for char_id, box in scene_report["screen_boxes"].items():
            assert box["x0"] >= 0.0, f"{char_id} cut off left in {label}"
            assert box["x1"] <= 1.0, f"{char_id} cut off right in {label}"
            assert box["y_top"] >= 0.0, f"{char_id} head cut off in {label}"
            assert box["y_bottom"] <= 1.0, f"{char_id} body cut off in {label}"
            assert box["y_top"] >= safe["top"] - 0.05, (
                f"{char_id} head inside the top safe band in {label}: {box['y_top']:.3f}"
            )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_portrait_and_landscape_solves_reach_different_distances_for_the_same_shot():
    """The same blocking must not use the same camera in both ratios.

    If this ever returns equal distances the format has stopped driving the
    camera, which is the whole point of Stage 5.3.
    """
    temp_dir = tempfile.mkdtemp(prefix="studio_framing_compare_")
    try:
        distances = {}
        for aspect, width, height in (("16:9", 1920, 1080), ("9:16", 1080, 1920)):
            project_id = "test_compare_project"
            job_id = f"job_compare_{aspect.replace(':', 'x')}"
            engine = BlenderAnimationEngineImpl(
                base_projects_dir=temp_dir,
                assets_dir=os.path.abspath("data/studio_assets"),
                keep_frames=False,
            )
            engine.render_animation(
                scene_graph=_vertical_render_graph(
                    SceneResolution(width=width, height=height, aspect_ratio=aspect, fps=30)
                ),
                project_id=project_id,
                job_id=job_id,
                engine_override="BLENDER_WORKBENCH",
                include_audio=False,
            )
            result_path = os.path.join(
                temp_dir, project_id, "renders", job_id, "render_result.json"
            )
            with open(result_path, encoding="utf-8") as handle:
                framing = json.load(handle)["framing"]
            solve = framing["scenes"][0]["solve"]
            distances[aspect] = {
                "distance_m": solve["distance_m"],
                "lens_mm": solve["lens_mm"],
                "subject_width_m": solve["subject_width_m"],
                "fill_width": solve["fill_width"],
            }

        assert distances["9:16"]["distance_m"] < distances["16:9"]["distance_m"]

        # Portrait narrows the *world* blocking so the camera can push in. On
        # screen the pair still reads wider apart, because a 9:16 frame shows far
        # less width than the cast it is holding; that is the cast filling the
        # frame, not the cast drifting out of it.
        assert (
            distances["9:16"]["subject_width_m"] < distances["16:9"]["subject_width_m"]
        ), distances
        assert distances["9:16"]["fill_width"] > distances["16:9"]["fill_width"]

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
