import os
import shutil
import tempfile
import pytest
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
