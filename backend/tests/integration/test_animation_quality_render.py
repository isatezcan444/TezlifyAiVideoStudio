"""Stage 5.5 — real Blender animation render tests.

Nothing here is asserted from a scene file or a log line alone: the renderer's
own `render_result.json`, the keyframes it wrote into the rig, and the decoded
frames of the MP4 it produced are the evidence. Behaviour that does not show up
in those is not claimed.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess

import pytest
from PIL import Image

from tezlify_studio.domain.enums.studio_status import (
    CameraAngle,
    CameraMovement,
    CharacterExpression,
    CharacterPose,
    MouthViseme,
)
from tezlify_studio.domain.value_objects.scene_graph import (
    CharacterPlacement,
    DialogueViseme,
    SceneBackground,
    SceneCamera,
    SceneCharacter,
    SceneDialogue,
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (
    BlenderAnimationEngineImpl,
)
from tezlify_studio.infrastructure.configuration.settings import settings

BLENDER_READY = bool(shutil.which("blender") or os.path.exists(
    "/Applications/Blender.app/Contents/MacOS/Blender"))
ASSETS_READY = os.path.exists(
    os.path.join(settings.resolved_studio_assets_dir, "characters", "char_ali", "char_ali.blend")
) or os.path.exists("data/studio_assets/characters/char_ali/char_ali.blend")

pytestmark = pytest.mark.skipif(
    not (BLENDER_READY and ASSETS_READY),
    reason="Blender or the builtin character assets are not available",
)

ALI = "char_ali"
AYSE = "char_ayse"


def visemes(count=8):
    return [
        DialogueViseme(time=i * 0.2, end_time=i * 0.2 + 0.16,
                       viseme=MouthViseme.OPEN if i % 2 else MouthViseme.CLOSED,
                       phoneme="a" if i % 2 else "b", confidence=0.6,
                       source="ctc_forced")
        for i in range(count)
    ]


def build_graph(fps=30, width=640, height=360, aspect="16:9", ali_audio=None,
                ayse_audio=None) -> SceneGraph:
    """Two characters, two lines each, so speaker and listener both occur twice."""
    return SceneGraph(
        project_id="stage55_test",
        title="Stage 5.5 Animasyon Testi",
        resolution=SceneResolution(width=width, height=height, aspect_ratio=aspect, fps=fps),
        characters=[SceneCharacter(id=ALI, name="Ali"), SceneCharacter(id=AYSE, name="Ayşe")],
        scenes=[
            StudioScene(
                scene_id="scene_a",
                duration_seconds=6.0,
                background=SceneBackground(asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(character_id=ALI, position=[-0.55, 0.0, 0.0],
                                       rotation_y=14.0, pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                    CharacterPlacement(character_id=AYSE, position=[0.55, 0.0, 0.0],
                                       rotation_y=-14.0, pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                ],
                dialogues=[
                    SceneDialogue(character_id=ALI, start_time=0.4, end_time=2.4,
                                  text="Merhaba Ayşe, bugün seni görmek çok güzel!",
                                  audio_file=ali_audio, visemes=visemes(10)),
                    SceneDialogue(character_id=AYSE, start_time=3.2, end_time=5.4,
                                  text="Gerçekten mi? Ben de seni görmekten mutluyum.",
                                  audio_file=ayse_audio, visemes=visemes(10)),
                ],
            )
        ],
    )


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("stage55_render")
    engine = BlenderAnimationEngineImpl(
        base_projects_dir=str(root / "projects"),
        assets_dir=os.path.abspath("data/studio_assets"),
        keep_frames=True,
    )
    meta = engine.render_animation(
        scene_graph=build_graph(),
        project_id="stage55_test",
        job_id="job_a",
        include_audio=False,
    )
    result_path = os.path.join(str(root), "projects", "stage55_test", "renders", "job_a",
                               "render_result.json")
    frames_dir = os.path.join(str(root), "projects", "stage55_test", "frames", "job_a")
    return {
        "meta": meta,
        "result": json.load(open(result_path)),
        "frames": sorted(glob.glob(os.path.join(frames_dir, "frame_*.png"))),
        "scene_blend": os.path.join(str(root), "projects", "stage55_test", "scenes",
                                    "scene_job_a.blend"),
        "root": str(root),
    }


# ---------------------------------------------------------------- the plan
def test_the_render_used_the_animation_plan(rendered):
    animation = rendered["result"]["animation"]
    assert animation["planned"] is True, animation
    assert animation["summary"]["clips_total"] > 0
    assert animation["summary"]["distinct_clips"] >= 6


def test_gestures_were_actually_scheduled_from_the_text(rendered):
    usage = rendered["result"]["animation"]["summary"]["clip_usage"]
    # "Merhaba" is a greeting, the second line is a question, both are cheerful.
    assert usage.get("greeting", 0) >= 1
    assert usage.get("ask_question", 0) + usage.get("surprised", 0) >= 1
    assert usage.get("listen_attentive", 0) >= 1, "the listener had no attending behaviour"


def test_speaker_and_listener_received_different_clip_sets(rendered):
    scenes = rendered["result"]["animation"]["scenes"]
    by_character = {entry["character_id"]: entry for entry in scenes}
    assert set(by_character) == {ALI, AYSE}
    assert by_character[ALI]["profile"] != by_character[AYSE]["profile"], (
        "both characters were given the same personality, so they would move alike"
    )


def test_many_channels_were_keyed_not_just_a_sway(rendered):
    for entry in rendered["result"]["animation"]["scenes"]:
        assert entry["keyed_channels"] > 150, entry


def test_the_rig_exposes_elbow_and_wrist_controls(rendered):
    entry = rendered["result"]["animation"]["scenes"][0]
    for control in ("elbow_l", "elbow_r", "wrist_l", "wrist_r"):
        assert control in entry["controls"], f"{control} missing from {entry['controls']}"


# ---------------------------------------------------------------- real motion
_PROBE = """
import bpy, json, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
out = {}
for obj in bpy.data.objects:
    if obj.animation_data is None or obj.animation_data.action is None:
        continue
    action = obj.animation_data.action
    per_object = {}
    for path in ("rotation_euler", "location", "scale"):
        for index in range(3):
            try:
                curve = action.fcurve_ensure_for_datablock(obj, path, index=index)
            except Exception:
                continue
            points = [(k.co[0], k.co[1]) for k in curve.keyframe_points]
            values = [value for _, value in points]
            if len(values) >= 2:
                per_object["%s[%d]" % (path, index)] = {
                    "keys": len(values),
                    "span": max(values) - min(values),
                    "min": min(values),
                    "max": max(values),
                    "points": points,
                }
    if per_object:
        out[obj.name] = per_object
out["__flags__"] = {
    obj.name: getattr(obj, "visible_shadow", True)
    for obj in bpy.data.objects if obj.name.endswith("__Mesh_Mouth")
}
print("RIG_JSON" + json.dumps(out))
"""


@pytest.fixture(scope="module")
def rig(tmp_path_factory, rendered):
    """Keyframes as Blender actually stored them, read by a headless subprocess.

    The application venv has no `bpy`, so this cannot import it; the same trick
    the renderer uses applies - hand the script to Blender and read stdout.
    """
    script = tmp_path_factory.mktemp("probe") / "rig_probe.py"
    script.write_text(_PROBE, encoding="utf-8")
    blender = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
    proc = subprocess.run(
        [blender, "-b", "--factory-startup", "--python", str(script), "--",
         rendered["scene_blend"]],
        capture_output=True, text=True,
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RIG_JSON")), None)
    assert line is not None, proc.stdout[-800:] + proc.stderr[-800:]
    return json.loads(line[len("RIG_JSON"):])


def _spans(rig, object_name):
    entry = rig.get(object_name, {})
    return {channel: value["span"] for channel, value in entry.items()}


def _pooled_spans(rig, suffixes, prefix=ALI):
    """Channel names repeat across objects, so they must be keyed by object."""
    pooled = {}
    for suffix in suffixes:
        for channel, span in _spans(rig, f"{prefix}__{suffix}").items():
            pooled[f"{suffix}:{channel}"] = span
    return pooled


def test_the_speaker_actually_bent_its_arm(rig, rendered):
    arms = _pooled_spans(rig, ("Anchor_Arm_R", "Anchor_Arm_L", "Mesh_Arm_R_Lower",
                               "Mesh_Arm_L_Lower", "Mesh_Hand_R", "Mesh_Hand_L"))
    assert arms, "no arm, elbow or hand channel was keyed"
    biggest = max(arms.values())
    assert biggest > 0.25, f"limbs barely moved: {arms}"


def test_the_elbow_and_wrist_are_driven_not_just_the_shoulder(rig):
    """The point of repivoting those meshes is that joints bend at the joint."""
    elbow = _pooled_spans(rig, ("Mesh_Arm_R_Lower", "Mesh_Arm_L_Lower"))
    wrist = _pooled_spans(rig, ("Mesh_Hand_R", "Mesh_Hand_L"))
    assert max(elbow.values(), default=0.0) > 0.1, elbow
    assert max(wrist.values(), default=0.0) > 0.05, wrist


def test_the_head_and_torso_move(rig):
    for prefix in (ALI, AYSE):
        head = _spans(rig, f"{prefix}__Anchor_Head")
        torso = _spans(rig, f"{prefix}__Anchor_Torso")
        assert max(head.values(), default=0.0) > 0.03, (prefix, head)
        assert max(torso.values(), default=0.0) > 0.01, (prefix, torso)


def test_brows_moved_for_the_expression(rig):
    brows = {}
    for suffix in ("Mesh_Brow_L", "Mesh_Brow_R"):
        brows.update({k: v for k, v in _spans(rig, f"{ALI}__{suffix}").items()
                      if k.startswith("location")})
    assert max(brows.values(), default=0.0) > 0.002, brows


def test_the_eyes_blinked(rig):
    eyes = _spans(rig, f"{ALI}__Mesh_EyeWhite_L")
    assert eyes.get("scale[2]", 0.0) > 0.3, f"eye did not close: {eyes}"
    entry = rig.get(f"{ALI}__Mesh_EyeWhite_L", {}).get("scale[2]", {})
    assert entry.get("min", 1.0) < 0.6, entry


# ---------------------------------------------------------------- lip sync kept
def test_measured_visemes_still_drive_the_mouth(rendered):
    speakers = rendered["result"]["lip_sync"]["scenes"][0]["speakers"]
    assert speakers[ALI]["mode"] == "viseme", speakers
    assert rendered["result"]["lip_sync"]["real_lip_sync"] is True


def test_the_listener_mouth_stayed_shut(rig, rendered):
    """Clips must never overwrite visemes.

    Ali speaks at 0.4-2.4 s and Ayşe answers at 3.2-5.4 s, so both mouths move
    at some point in this scene. What must hold is that a character's mouth is
    at rest while the other one is talking.
    """
    fps = build_graph().resolution.fps
    ali_line = build_graph().scenes[0].dialogues[0]
    ali_start = int(round(ali_line.start_time * fps))
    ali_end = int(round(ali_line.end_time * fps))

    def _mouth_points(character_id):
        curve = rig.get(f"{character_id}__Mesh_Mouth", {}).get("scale[1]", {})
        return curve.get("points", []), curve

    def _value_at(points, frame):
        ordered = sorted(points)
        if not ordered or frame <= ordered[0][0]:
            return ordered[0][1]
        if frame >= ordered[-1][0]:
            return ordered[-1][1]
        for (f0, v0), (f1, v1) in zip(ordered, ordered[1:]):
            if f0 <= frame <= f1:
                span = f1 - f0
                return v0 if span == 0 else v0 + (v1 - v0) * (frame - f0) / span
        return ordered[-1][1]

    ali_points, ali_curve = _mouth_points(ALI)
    ayse_points, _ = _mouth_points(AYSE)
    assert ali_curve.get("span", 0.0) > 0.05, f"speaker mouth did not move: {ali_curve}"
    assert ayse_points, "the listener's mouth was never keyed"

    during_ali = [_value_at(ayse_points, frame) for frame in range(ali_start, ali_end + 1)]
    spread = max(during_ali) - min(during_ali)
    assert spread < 0.02, (
        f"listener mouth moved {spread:.3f} while {ALI} was speaking "
        f"(frames {ali_start}-{ali_end}): {min(during_ali)}..{max(during_ali)}"
    )
    ali_moving = [_value_at(ali_points, frame) for frame in range(ali_start, ali_end + 1)]
    assert max(ali_moving) - min(ali_moving) > 0.05, ali_moving

    # "Not moving" is not enough: the asset's rest mouth has parted lips and
    # reads as open. The listener must sit at the same closed pose the speaker
    # holds on the frame before speech, not at the built rest scale.
    ali_closed = _value_at(ali_points, ali_start - 1)
    assert ali_closed < 0.5, f"speaker pre-speech mouth was not closed: {ali_closed}"
    assert max(during_ali) <= ali_closed + 0.02, (
        f"listener mouth held at {max(during_ali)} instead of the closed pose "
        f"{ali_closed}"
    )


def test_a_silent_mouth_does_not_read_as_open(rig):
    """The closed pose alone was not enough in close-ups.

    The mouth is a flat disc proud of the face: its cast shadow drew a black
    crescent under the lip, and the teeth strip peeked above it. Both made a
    correctly closed mouth look open, so the mouth must never cast a shadow and
    the teeth must only be full size while that character is speaking.
    """
    mouths = {name: value for name, value in rig.get("__flags__", {}).items()
              if name.endswith("__Mesh_Mouth")}
    assert len(mouths) == 2, f"expected two mouth objects, got {mouths}"
    assert all(value is False for value in mouths.values()), mouths

    for prefix in (ALI, AYSE):
        curve = rig.get(f"{prefix}__Mesh_Teeth", {}).get("scale[0]")
        assert curve is not None, f"{prefix} teeth were never keyed"
        assert curve["max"] >= 0.9, f"{prefix} teeth never came back for speech: {curve}"
        assert curve["min"] <= 0.01, f"{prefix} teeth stayed visible while silent: {curve}"


# ---------------------------------------------------------------- camera
def test_the_camera_followed_the_shot_plan(rendered):
    shots = [entry["shot_kind"] for entry in rendered["result"]["framing"]["scenes"]]
    assert len(shots) >= 3, f"expected several shot windows, got {shots}"
    assert "establishing" in shots
    assert "listener_reaction" in shots


def test_every_shot_kept_the_cast_in_the_safe_area(rendered):
    for entry in rendered["result"]["framing"]["scenes"]:
        assert entry["solve"]["fits_safe_area"] is True, entry["shot_kind"]


def test_close_up_uses_a_longer_lens_than_the_two_shot(rendered):
    by_kind = {e["shot_kind"]: e["solve"]["lens_mm"] for e in rendered["result"]["framing"]["scenes"]}
    if "speaker_close_up" in by_kind:
        assert by_kind["speaker_close_up"] > by_kind["two_shot"]


# ---------------------------------------------------------------- colour
def test_the_render_is_not_grey_clay(rendered):
    """Character Studio colours must survive into the MP4.

    Mean HSV saturation of the reference grey render measured 0.4; the coloured
    render measures around 60. Anything under 8 would mean the palette was lost.
    """
    sample = rendered["frames"][len(rendered["frames"]) // 2]
    with Image.open(sample) as im:
        saturation = im.convert("HSV").split()[1]
        mean_sat = sum(saturation.histogram()[i] * i for i in range(256)) / saturation.size[0] / 255
    assert mean_sat > 0.03, f"frame mean saturation {mean_sat:.4f} means untextured grey"


def test_the_engine_is_the_one_we_asked_for(rendered):
    assert rendered["result"]["engine_config"]["engine"] == "BLENDER_EEVEE"
    assert rendered["result"]["engine_config"]["view_transform"] == "Standard"
    assert rendered["result"]["engine_config"]["color_sync"]["synced"] > 0


# ---------------------------------------------------------------- output
def test_the_video_decodes_completely_and_is_valid_h264(rendered):
    path = rendered["meta"].video_file_path
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,codec_type,width,height,pix_fmt:format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(probe.stdout)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert decode.returncode == 0, decode.stderr


def test_a_silent_render_is_labelled_silent(rendered):
    """include_audio=False means there is no speech; the metadata must say so
    instead of reporting a video with sound."""
    meta = rendered["meta"]
    assert meta.has_audio is False
    assert meta.audio_audible is False
    assert meta.audio_mean_db is None
    assert "no audio stream" in meta.audio_reason


@pytest.fixture(scope="module")
def rendered_with_speech(tmp_path_factory):
    """The same scene, but with real audio files attached to both lines."""
    root = tmp_path_factory.mktemp("stage55_render_audio")
    tone = str(root / "line.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "sine=frequency=180:duration=1.8:sample_rate=44100", "-af", "volume=0.35", tone],
        check=True, capture_output=True,
    )
    engine = BlenderAnimationEngineImpl(
        base_projects_dir=str(root / "projects"),
        assets_dir=os.path.abspath("data/studio_assets"),
        keep_frames=False,
    )
    meta = engine.render_animation(
        scene_graph=build_graph(ali_audio=tone, ayse_audio=tone),
        project_id="stage55_test",
        job_id="job_audio",
        include_audio=True,
    )
    return meta


def test_the_dialogue_audio_ends_up_in_the_mp4(rendered_with_speech):
    """A render is not finished-with-sound unless the audio measures audible."""
    path = rendered_with_speech.video_file_path
    meta = rendered_with_speech
    assert meta.has_audio is True, meta.audio_reason
    assert meta.audio_codec == "aac"
    assert meta.audio_audible is True, meta.audio_reason
    assert meta.audio_mean_db is not None and meta.audio_mean_db > -60.0

    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    ).stdout)
    audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert audio, probe
    assert audio[0]["codec_name"] == "aac"
