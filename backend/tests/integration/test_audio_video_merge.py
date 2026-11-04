import os
import json
import shutil
import subprocess
import tempfile
import pytest

from tezlify_studio.domain.enums.studio_status import (
    CameraAngle,
    CameraMovement,
    CharacterPose,
    CharacterExpression,
)
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    SceneResolution,
    SceneCharacter,
    StudioScene,
    SceneBackground,
    SceneCamera,
    CharacterPlacement,
    SceneDialogue,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import BlenderAnimationEngineImpl


def create_mock_dialogue_mp3(output_path: str, duration_sec: float, freq: int = 1000):
    """Generates a valid MP3 file using FFmpeg lavfi sine tone."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration_sec}",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def test_end_to_end_audio_video_merge():
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_dir = os.path.join(tmp_dir, "audios")
        output_mp4 = os.path.join(tmp_dir, "test_merged_output.mp4")

        # 1. Create two dialogue MP3 files
        dlg1_path = os.path.join(audio_dir, "ali_dlg1.mp3")
        dlg2_path = os.path.join(audio_dir, "ayse_dlg2.mp3")

        create_mock_dialogue_mp3(dlg1_path, duration_sec=1.5, freq=440)
        create_mock_dialogue_mp3(dlg2_path, duration_sec=1.8, freq=880)

        assert os.path.exists(dlg1_path) and os.path.getsize(dlg1_path) > 1000
        assert os.path.exists(dlg2_path) and os.path.getsize(dlg2_path) > 1000

        # 2. Build SceneGraph with dialogues referencing audio files
        scene_graph = SceneGraph(
            schema_version="1.0",
            project_id="test_proj_audio_merge",
            title="Audio Merge Integration Test",
            resolution=SceneResolution(width=640, height=360, fps=24),
            characters=[
                SceneCharacter(id="char_ali", name="Ali", voice_id="IKne3meq5aSn9XLyUdCD"),
                SceneCharacter(id="char_ayse", name="Ayşe", voice_id="cgSgspJ2msm6clMCkdW9"),
            ],
            scenes=[
                StudioScene(
                    scene_id="scene_01",
                    duration_seconds=4.0,
                    background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                    camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                    character_placements=[
                        CharacterPlacement(
                            character_id="char_ali",
                            position=[-0.7, 0.0, 0.0],
                            rotation_y=30.0,
                            expression=CharacterExpression.CHEERFUL,
                            pose=CharacterPose.SITTING_TABLE,
                        ),
                        CharacterPlacement(
                            character_id="char_ayse",
                            position=[0.7, 0.0, 0.0],
                            rotation_y=-30.0,
                            expression=CharacterExpression.CHEERFUL,
                            pose=CharacterPose.SITTING_TABLE,
                        ),
                    ],
                    dialogues=[
                        SceneDialogue(
                            character_id="char_ali",
                            text="Merhaba Ayşe!",
                            start_time=0.5,
                            end_time=2.0,
                            audio_file=dlg1_path,
                        ),
                        SceneDialogue(
                            character_id="char_ayse",
                            text="Selam Ali, nasılsın?",
                            start_time=2.1,
                            end_time=3.9,
                            audio_file=dlg2_path,
                        ),
                    ],
                )
            ],
        )

        # 3. Render using BlenderAnimationEngineImpl
        engine = BlenderAnimationEngineImpl(base_projects_dir=tmp_dir)
        project_id = "test_audio_proj"
        job_id = "job_test_01"
        expected_output_mp4 = os.path.join(tmp_dir, project_id, "renders", job_id, f"{job_id}.mp4")

        metadata = engine.render_animation(
            scene_graph=scene_graph,
            project_id=project_id,
            job_id=job_id,
            engine_override="BLENDER_WORKBENCH",
        )

        # 4. Verify Technical Output
        assert os.path.exists(expected_output_mp4)
        assert os.path.getsize(expected_output_mp4) > 10000
        assert metadata.has_audio is True
        assert metadata.audio_codec == "aac"
        assert metadata.video_codec == "h264"
        assert metadata.width == 640
        assert metadata.height == 360
        assert metadata.fps == 24
        assert 3.5 <= metadata.duration_seconds <= 4.5

        # 5. Independent validation via ffprobe
        probe_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            expected_output_mp4,
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(res.stdout)

        streams = probe_data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        assert v_stream is not None, "Video stream missing from output MP4"
        assert a_stream is not None, "Audio stream missing from output MP4"

        assert v_stream["codec_name"] == "h264"
        assert a_stream["codec_name"] == "aac"
        assert int(a_stream.get("sample_rate", 0)) == 44100
        assert a_stream.get("channels") == 2
