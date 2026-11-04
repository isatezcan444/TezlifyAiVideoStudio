import pytest
from datetime import datetime, timezone
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.domain.exceptions.studio_exceptions import (
    RenderJobNotFoundException,
    InvalidRenderStateException,
)
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    StudioScene,
    SceneCharacter,
    CharacterPlacement,
    SceneDialogue,
    SceneResolution,
    CharacterPose,
    CharacterExpression,
)

def test_render_job_lifecycle():
    job = RenderJob(
        id="job_test_001",
        project_id="proj_001",
        status=RenderJobStatus.PENDING,
        progress_percent=0.0,
        current_step="Pending",
    )
    assert job.status == RenderJobStatus.PENDING
    assert job.progress_percent == 0.0
    assert job.started_at is None
    assert job.completed_at is None

    # Start
    job.start("Blender engine initialized")
    assert job.status == RenderJobStatus.RUNNING
    assert job.progress_percent == 5.0
    assert job.started_at is not None

    # Update progress
    job.update_progress(45.0, "Rendering frames headless")
    assert job.progress_percent == 45.0
    assert job.current_step == "Rendering frames headless"

    # Progress bounds clamping
    job.update_progress(150.0, "Clamping")
    assert job.progress_percent == 100.0
    job.update_progress(-10.0, "Clamping lower")
    assert job.progress_percent == 0.0

    # Complete
    metadata = RenderOutputMetadata(
        video_file_path="/path/to/test.mp4",
        file_size_bytes=1048576,
        duration_seconds=15.0,
        width=1920,
        height=1080,
        fps=30,
        video_codec="h264",
        pixel_format="yuv420p",
        container="mp4",
        frame_count=450,
        render_duration_seconds=18.5,
        engine="BLENDER_WORKBENCH",
    )
    job.complete(video_path=metadata.video_file_path, metadata=metadata)
    assert job.status == RenderJobStatus.COMPLETED
    assert job.progress_percent == 100.0
    assert job.output_video_path == "/path/to/test.mp4"
    assert job.output_metadata == metadata
    assert job.completed_at is not None

def test_render_job_failure():
    job = RenderJob(
        id="job_fail_001",
        project_id="proj_001",
    )
    job.start()
    job.fail("Blender crash: Out of memory")
    assert job.status == RenderJobStatus.FAILED
    assert job.error_message == "Blender crash: Out of memory"
    assert "Failed" in job.current_step
    assert job.completed_at is not None

def test_render_job_cancel():
    job = RenderJob(
        id="job_cancel_001",
        project_id="proj_001",
    )
    job.start()
    job.cancel()
    assert job.status == RenderJobStatus.CANCELLED
    assert job.current_step == "Cancelled"

def test_render_metadata_validation():
    meta = RenderOutputMetadata(
        video_file_path="/output/video.mp4",
        file_size_bytes=2048000,
        duration_seconds=10.0,
        width=1920,
        height=1080,
        fps=30,
    )
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.fps == 30
    assert meta.video_codec == "h264"
    assert meta.pixel_format == "yuv420p"

    data = meta.model_dump()
    assert data["file_size_bytes"] == 2048000
    restored = RenderOutputMetadata.model_validate(data)
    assert restored.duration_seconds == 10.0

def test_timeline_frame_calculation_across_fps():
    duration_seconds = 15.0
    for fps in (24, 25, 30, 60):
        total_frames = int(round(duration_seconds * fps))
        assert total_frames == int(duration_seconds * fps)

def test_scene_graph_timing_and_framing():
    sg = SceneGraph(
        schema_version="1.0",
        project_id="proj_test_timing",
        title="Timing Test Project",
        resolution=SceneResolution(width=1920, height=1080, fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_01",
                duration_seconds=5.0,
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ali",
                        position=[-0.7, 0.0, 0.0],
                        rotation_y=45.0,
                        pose=CharacterPose.STANDING,
                        expression=CharacterExpression.CHEERFUL,
                    ),
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.7, 0.0, 0.0],
                        rotation_y=-45.0,
                        pose=CharacterPose.STANDING,
                        expression=CharacterExpression.NEUTRAL,
                    ),
                ],
                dialogues=[
                    SceneDialogue(
                        character_id="char_ali",
                        start_time=1.0,
                        end_time=3.5,
                        text="Merhaba!",
                    )
                ],
            ),
            StudioScene(
                scene_id="scene_02",
                duration_seconds=7.0,
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.0, 0.0, 0.0],
                        pose=CharacterPose.SITTING,
                    )
                ],
            ),
        ],
    )
    assert sg.total_duration_seconds == 12.0
    fps = sg.resolution.fps
    total_frames = int(round(sg.total_duration_seconds * fps))
    assert total_frames == 360

def test_render_exceptions():
    exc = RenderJobNotFoundException("job_xyz")
    assert exc.job_id == "job_xyz"
    assert "job_xyz" in exc.message
    assert exc.error_code == "RENDER_JOB_NOT_FOUND"

    state_exc = InvalidRenderStateException("Render running")
    assert state_exc.error_code == "INVALID_RENDER_STATE"
