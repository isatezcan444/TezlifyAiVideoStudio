"""Stage 5.4 — real Blender lip-sync render tests.

These run the actual render worker with real dialogue audio and real alignment.
Behaviour that is not verified on rendered frames is not claimed here: the tests
read the keyframes and mouth transforms the renderer actually produced.
"""

import json
import os
import shutil
import subprocess
import tempfile

import pytest
from PIL import Image, ImageChops

from tezlify_studio.application.services.lip_sync_resolver import LipSyncResolver
from tezlify_studio.domain.enums.studio_status import (
    AlignmentSource,
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
from tezlify_studio.infrastructure.alignment.ctc_forced_alignment_impl import (
    CTCForcedAlignmentImpl,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (
    BlenderAnimationEngineImpl,
)
from tezlify_studio.infrastructure.configuration.settings import settings

ALIGNMENT_READY = bool(settings.alignment_python_executable) and settings.lip_sync_enabled

pytestmark = pytest.mark.skipif(
    not ALIGNMENT_READY,
    reason=(
        "isolated alignment environment not present "
        "(tools/alignment-venv); real lip-sync render tests require it"
    ),
)

TEXT = "Merhaba Ayşe, bugün nasılsın?"


@pytest.fixture(scope="module")
def turkish_speech(tmp_path_factory):
    """Real Turkish speech from the macOS system voice, as the pipeline uses it."""
    directory = tmp_path_factory.mktemp("lipsync_speech")
    ali = directory / "ali.mp3"
    ayse = directory / "ayse.mp3"
    for path, text in ((ali, TEXT), (ayse, "Çocuklar dışarıda oyun oynuyor.")):
        aiff = str(path) + ".aiff"
        subprocess.run(["say", "-v", "Yelda", "-r", "170", "-o", aiff, text], check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", aiff, "-c:a", "libmp3lame",
             "-b:a", "128k", str(path)],
            check=True,
        )
        os.remove(aiff)
    return str(ali), str(ayse)


def probe_duration(path: str) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip())


def build_graph(ali_audio: str, ayse_audio: str, fps: int, duration: float) -> SceneGraph:
    ali_end = round(0.4 + probe_duration(ali_audio), 3)
    ayse_start = round(ali_end + 0.6, 3)
    ayse_end = round(ayse_start + probe_duration(ayse_audio), 3)
    scene_duration = max(duration, ayse_end + 0.8)
    width, height, aspect = (1080, 1920, "9:16")

    return SceneGraph(
        project_id="proj_lipsync_render",
        title="Stage 5.4 Lip Sync Render Testi",
        resolution=SceneResolution(width=width, height=height, aspect_ratio=aspect, fps=fps),
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_01",
                duration_seconds=scene_duration,
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
                dialogues=[
                    SceneDialogue(character_id="char_ali", start_time=0.4, end_time=ali_end,
                                  text=TEXT, audio_file=ali_audio),
                    SceneDialogue(character_id="char_ayse", start_time=ayse_start,
                                  end_time=ayse_end,
                                  text="Çocuklar dışarıda oyun oynuyor.",
                                  audio_file=ayse_audio),
                ],
            )
        ],
    )


def render(temp_dir, graph, job_id, keep_frames=True):
    engine = BlenderAnimationEngineImpl(
        base_projects_dir=temp_dir,
        assets_dir=os.path.abspath("data/studio_assets"),
        keep_frames=keep_frames,
    )
    metadata = engine.render_animation(
        scene_graph=graph, project_id="proj_lipsync_render", job_id=job_id,
        engine_override="BLENDER_WORKBENCH", include_audio=False,
    )
    result_path = os.path.join(
        temp_dir, "proj_lipsync_render", "renders", job_id, "render_result.json"
    )
    with open(result_path, encoding="utf-8") as handle:
        worker_result = json.load(handle)
    frames_dir = os.path.join(temp_dir, "proj_lipsync_render", "frames", job_id)
    return metadata, worker_result, frames_dir


@pytest.fixture
def project_dir():
    """A temp project tree that survives until after the test's assertions.

    Frames are what these tests measure, so the directory cannot be removed when
    the render returns — it has to outlive the assertions that read the PNGs.
    """
    path = tempfile.mkdtemp(prefix="studio_lipsync_")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def align_then_render(graph, temp_dir, job_id="lipsync"):
    """Resolve real alignment for this exact audio, then render it."""
    provider = CTCForcedAlignmentImpl(
        python_executable=settings.alignment_python_executable,
        model_id=settings.alignment_model_id,
        cache_dir=settings.alignment_cache_dir,
        model_cache_dir=settings.alignment_model_cache_dir,
    )
    resolved, report = LipSyncResolver(provider).resolve(graph)
    metadata, worker_result, frames_dir = render(temp_dir, resolved, job_id)
    return metadata, worker_result, frames_dir, report, resolved


# ---------------------------------------------------------------------------
# Alignment reaches the renderer
# ---------------------------------------------------------------------------

def test_real_alignment_produces_viseme_driven_mouth_keyframes(turkish_speech, project_dir):
    ali, ayse = turkish_speech
    graph = build_graph(ali, ayse, fps=30, duration=6.0)

    metadata, worker_result, frames_dir, report, resolved = align_then_render(graph, project_dir)

    assert report.dialogues_aligned == 2, report.to_dict()
    assert report.uses_real_alignment
    assert worker_result["lip_sync"]["real_lip_sync"] is True

    scene_report = worker_result["lip_sync"]["scenes"][0]
    speakers = scene_report["speakers"]
    assert set(speakers) == {"char_ali", "char_ayse"}
    for char_id, mode in speakers.items():
        assert mode["mode"] == "viseme", (char_id, mode)
        assert mode["source"] == AlignmentSource.CTC_FORCED.value
        assert mode["segments"] > 8, f"{char_id} got only {mode['segments']} segments"
        assert mode["keyframes"] == len(mode["frames"])

    # The renderer must be keying at the aligner's times, not a fixed cycle.
    ali_dialogue = resolved.scenes[0].dialogues[0]
    fps = metadata.fps
    abs_start = 1 + int(round(ali_dialogue.start_time * fps))
    expected = {abs_start + int(round(v.time * fps)) for v in ali_dialogue.visemes}
    keyed = set(speakers["char_ali"]["frames"])
    assert expected <= keyed | {max(1, abs_start - 1), abs_start + int(round(
        (ali_dialogue.end_time - ali_dialogue.start_time) * fps))}


def test_mouth_actually_moves_between_visemes_on_rendered_frames(turkish_speech, project_dir):
    ali, ayse = turkish_speech
    graph = build_graph(ali, ayse, fps=30, duration=6.0)

    metadata, worker_result, frames_dir, report, resolved = align_then_render(graph, project_dir)

    scene_report = worker_result["lip_sync"]["scenes"][0]
    boxes = scene_report["mouth_boxes"]
    assert boxes, "renderer reported no mouth position"

    dialogue = resolved.scenes[0].dialogues[0]
    fps = metadata.fps
    abs_start = 1 + int(round(dialogue.start_time * fps))

    by_viseme = {}
    for viseme in dialogue.visemes:
        frame = abs_start + int(round(viseme.time * fps))
        key = str(frame)
        if key not in boxes or "char_ali" not in boxes[key]:
            continue
        by_viseme.setdefault(viseme.viseme.value, (frame, boxes[key]["char_ali"]["screen"]))

    if "CLOSED" not in by_viseme or "OPEN" not in by_viseme:
        pytest.fail(
            f"alignment produced no CLOSED/OPEN pair to compare: {sorted(by_viseme)}"
        )

    closed_frame, _ = by_viseme["CLOSED"]
    open_frame, open_screen = by_viseme["OPEN"]
    closed_path = os.path.join(frames_dir, f"frame_{closed_frame:04d}.png")
    open_path = os.path.join(frames_dir, f"frame_{open_frame:04d}.png")
    assert os.path.isfile(closed_path) and os.path.isfile(open_path)

    with Image.open(open_path) as probe:
        width, height = probe.size
    screen = open_screen
    box_w = max(24, int((screen["x1"] - screen["x0"]) * width * 2.4))
    box_h = max(24, int((screen["y_bottom"] - screen["y_top"]) * height * 2.4))
    cx = int((screen["x0"] + screen["x1"]) / 2 * width)
    cy = int((screen["y_top"] + screen["y_bottom"]) / 2 * height)
    box = (max(0, cx - box_w // 2), max(0, cy - box_h // 2),
           min(width, cx + box_w // 2), min(height, cy + box_h // 2))

    with Image.open(closed_path) as a, Image.open(open_path) as b:
        diff = ImageChops.difference(a.convert("RGB").crop(box), b.convert("RGB").crop(box))
    data = diff.convert("L").tobytes()
    changed = sum(1 for value in data if value > 12) / len(data)

    assert changed > 0.15, (
        f"OPEN and CLOSED differ by only {changed:.2%} in the mouth region — "
        "the viseme poses are not reaching the rendered frames"
    )


# ---------------------------------------------------------------------------
# Listener isolation and speech boundaries
# ---------------------------------------------------------------------------

def test_listener_mouth_stays_at_rest_while_the_partner_speaks(turkish_speech, project_dir):
    ali, ayse = turkish_speech
    graph = build_graph(ali, ayse, fps=30, duration=6.0)

    metadata, worker_result, frames_dir, report, resolved = align_then_render(graph, project_dir)

    fps = metadata.fps
    ali_dialogue, ayse_dialogue = resolved.scenes[0].dialogues
    ayse_start_frame = 1 + int(round(ayse_dialogue.start_time * fps))
    ali_end_frame = 1 + int(round(ali_dialogue.end_time * fps))

    # During Ayşe's line, Ali's mouth must hold the closed baseline the scene
    # starts from, not the asset's parted rest mouth.
    boxes = worker_result["lip_sync"]["scenes"][0]["mouth_boxes"]
    mid_ayse = ayse_start_frame + 3
    key = str(mid_ayse)
    if key not in boxes:
        key = min(boxes, key=lambda k: abs(int(k) - mid_ayse))
    ali_height = boxes[key]["char_ali"]["world_height_m"]

    rest_key = str(1)
    rest_height = boxes[rest_key]["char_ali"]["world_height_m"] if rest_key in boxes else None
    if rest_height is None:
        nearest = min(boxes, key=lambda k: abs(int(k) - ali_end_frame))
        rest_height = boxes[nearest]["char_ali"]["world_height_m"]

    # A closed mouth sits within a couple of millimetres of the scene baseline.
    assert abs(ali_height - rest_height) < 0.012, (
        f"Ali's mouth height during Ayşe's line ({ali_height}) differs from rest "
        f"({rest_height}) — the listener is animating"
    )


def test_mouth_returns_to_rest_after_speech_ends(turkish_speech, project_dir):
    ali, ayse = turkish_speech
    graph = build_graph(ali, ayse, fps=30, duration=6.0)

    metadata, worker_result, frames_dir, report, resolved = align_then_render(graph, project_dir)

    fps = metadata.fps
    ali_dialogue = resolved.scenes[0].dialogues[0]
    last_viseme_frame = 1 + int(round(
        (ali_dialogue.start_time + ali_dialogue.visemes[-1].end_time) * fps
    ))

    boxes = worker_result["lip_sync"]["scenes"][0]["mouth_boxes"]
    keyed_frames = sorted(int(k) for k in boxes)
    after = [f for f in keyed_frames if f > last_viseme_frame + 2]
    if not after:
        pytest.skip("render too short to sample after the last viseme")

    # Compare against the widest open pose seen during speech.
    heights = {f: boxes[str(f)]["char_ali"]["world_height_m"] for f in keyed_frames}
    during = [h for f, h in heights.items() if f <= last_viseme_frame]
    after_height = heights[after[0]]
    assert after_height <= max(during) - 0.004, (
        f"mouth still {after_height} m tall after speech (max during "
        f"speech {max(during)} m) — it did not close"
    )


# ---------------------------------------------------------------------------
# Frame-rate independence (no hardcoded 30 fps)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fps", [24, 25, 30, 60])
def test_viseme_keyframes_are_proportional_to_the_scene_fps(turkish_speech, fps, project_dir):
    """The frame rate comes from the SceneGraph, never from a hardcoded 30."""
    ali, _ = turkish_speech
    graph = build_graph(ali, ali, fps=fps, duration=6.0)

    metadata, worker_result, _frames, report, resolved = align_then_render(
        graph, project_dir, job_id=f"fps_{fps}"
    )

    assert metadata.fps == fps
    speakers = worker_result["lip_sync"]["scenes"][0]["speakers"]
    assert speakers["char_ali"]["mode"] == "viseme"

    dialogue = resolved.scenes[0].dialogues[0]
    abs_start = 1 + int(round(dialogue.start_time * fps))
    keyed = speakers["char_ali"]["frames"][1:-1]
    assert len(keyed) == len(dialogue.visemes)
    for viseme, frame in zip(dialogue.visemes, keyed):
        expected = abs_start + int(round(viseme.time * fps))
        assert frame == expected, (
            f"fps={fps}: viseme at {viseme.time}s keyed at frame {frame}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Fallback honesty
# ---------------------------------------------------------------------------

def test_graph_without_alignment_keeps_the_legacy_flap_and_says_so(turkish_speech):
    ali, ayse = turkish_speech
    graph = build_graph(ali, ayse, fps=30, duration=6.0)

    temp_dir = tempfile.mkdtemp(prefix="studio_lipsync_fallback_")
    try:
        engine = BlenderAnimationEngineImpl(
            base_projects_dir=temp_dir,
            assets_dir=os.path.abspath("data/studio_assets"),
            keep_frames=False,
        )
        metadata = engine.render_animation(
            scene_graph=graph, project_id="proj_lipsync_render", job_id="fallback",
            engine_override="BLENDER_WORKBENCH", include_audio=False,
        )
        result_path = os.path.join(
            temp_dir, "proj_lipsync_render", "renders", "fallback", "render_result.json"
        )
        with open(result_path, encoding="utf-8") as handle:
            worker_result = json.load(handle)

        assert metadata.width == 1080 and metadata.height == 1920
        assert worker_result["lip_sync"]["real_lip_sync"] is False
        for mode in worker_result["lip_sync"]["scenes"][0]["speakers"].values():
            assert mode["mode"] == "legacy_flap"
            assert mode["source"] == "estimated"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_legacy_planner_visemes_are_not_mistaken_for_measured_alignment(
    turkish_speech, project_dir
):
    """The story planner writes placeholder visemes; they must not count as lip sync.

    Checked through a real render rather than by importing the worker, which only
    runs inside Blender. If placeholders were ever accepted, the render would
    report viseme mode and this would fail.
    """
    ali, ayse = turkish_speech
    graph = build_graph(ali, ayse, fps=30, duration=6.0)
    for dialogue in graph.scenes[0].dialogues:
        # Exactly what template_story_planner writes: no source, no end_time.
        dialogue.visemes = [
            DialogueViseme(time=index * 0.35) for index in range(4)
        ]

    _metadata, worker_result, _frames = render(project_dir, graph, "placeholders")

    lip_sync = worker_result["lip_sync"]
    assert lip_sync["real_lip_sync"] is False
    for char_id, mode in lip_sync["scenes"][0]["speakers"].items():
        assert mode["mode"] == "legacy_flap", (
            f"{char_id} used {mode['mode']} from placeholder visemes"
        )
        assert mode["segments"] == 0
        assert mode["source"] == "estimated"
