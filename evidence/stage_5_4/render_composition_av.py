#!/usr/bin/env python3
"""Stage 5.4 evidence: the full production chain, ending in an A/V file.

The other evidence scripts stop at the Blender scene clip. This one runs the
whole documented flow — SceneDialogue -> audio -> alignment -> visemes ->
Blender keyframes -> FFmpeg composition with AAC audio — so the lip-sync claim is
backed by the same muxed MP4 a user would download, not only by a silent clip.

Alignment results are read from the content-addressed cache, so this is fast.

Usage:
    PYTHONPATH=backend/src .venv/bin/python evidence/stage_5_4/render_composition_av.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))
sys.path.insert(0, os.path.join(REPO, "evidence", "stage_5_3"))

from measure import ffprobe_summary, measure_frame, write_json  # noqa: E402
from tezlify_studio.application.services.lip_sync_resolver import LipSyncResolver  # noqa: E402
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
    SceneDialogue,
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.domain.value_objects.video_composition import (  # noqa: E402
    CompositionScene,
    CompositionTransition,
    SubtitleSettings,
    VideoComposition,
    VideoFormat,
)
from tezlify_studio.infrastructure.alignment.ctc_forced_alignment_impl import (  # noqa: E402
    CTCForcedAlignmentImpl,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (  # noqa: E402
    BlenderAnimationEngineImpl,
)
from tezlify_studio.infrastructure.configuration.settings import settings  # noqa: E402
from tezlify_studio.infrastructure.video.ffmpeg_composition_engine import (  # noqa: E402
    FFmpegCompositionEngine,
)

OUT = os.path.join(HERE, "composition_av")
PROJECT_ID = "stage54_composition_av"

LINES = [
    ("char_ali", "Merhaba Ayşe, bugün nasılsın?"),
    ("char_ayse", "Çocuklar dışarıda oyun oynuyor."),
    ("char_ali", "Üç küçük kuş ağaçta ötüyor."),
]


def duration_of(path: str) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip())


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    audio_dir = os.path.join(REPO, "data", "audio_cache", "stage_5_4")

    # Reuse the exact dialogue audio produced by render_lipsync_demo.py so the
    # alignment cache is a hit and the two artefacts describe the same speech.
    audio_files = []
    for index in range(1, len(LINES) + 1):
        speaker = LINES[index - 1][0]
        path = os.path.join(audio_dir, f"line_{index}_{speaker}.mp3")
        if not os.path.isfile(path):
            raise SystemExit(f"missing dialogue audio {path}; run render_lipsync_demo.py first")
        audio_files.append((path, duration_of(path)))

    cursor = 0.4
    dialogues = []
    for (speaker, text), (path, duration) in zip(LINES, audio_files):
        start = cursor
        end = round(start + duration, 3)
        dialogues.append(SceneDialogue(
            character_id=speaker, start_time=start, end_time=end,
            text=text, audio_file=path,
        ))
        cursor = round(end + 0.6, 3)
    scene_duration = round(cursor + 0.6, 3)

    graph = SceneGraph(
        project_id=PROJECT_ID,
        title="Stage 5.4 Kompozisyon A/V Kanıtı",
        resolution=SceneResolution(width=1080, height=1920, aspect_ratio="9:16", fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_av",
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
                dialogues=dialogues,
            )
        ],
    )

    print("1. Resolve alignment for this exact audio (cache expected)")
    provider = CTCForcedAlignmentImpl(
        python_executable=settings.alignment_python_executable,
        model_id=settings.alignment_model_id,
        cache_dir=settings.alignment_cache_dir,
        model_cache_dir=settings.alignment_model_cache_dir,
    )
    resolved, report = LipSyncResolver(provider).resolve(graph)
    print(f"   {report.to_dict()}")
    assert report.dialogues_aligned == len(LINES), report.to_dict()

    print("\n2. FFmpeg composition (9:16, AAC, Turkish subtitles)")
    engine = BlenderAnimationEngineImpl(
        base_projects_dir=os.path.join(REPO, "data", "studio_projects"),
        assets_dir=os.path.join(REPO, "data", "studio_assets"),
    )
    composition_engine = FFmpegCompositionEngine(
        animation_engine=engine,
        base_projects_dir=engine.base_projects_dir,
    )
    composition = VideoComposition(
        id=f"comp_{PROJECT_ID}",
        project_id=PROJECT_ID,
        name="Stage 5.4 A/V Kanıtı",
        format=VideoFormat.PORTRAIT_9_16,
        fps=30,
        scenes=[CompositionScene(scene_id="scene_av", transition=CompositionTransition.CUT)],
        subtitles=SubtitleSettings(enabled=True, burn_in=True, save_srt=True),
    )
    job_id = "comp_av_9x16"
    metadata = composition_engine.render_composition(
        scene_graph=resolved,
        composition=composition,
        project_id=PROJECT_ID,
        job_id=job_id,
        engine_override="BLENDER_WORKBENCH",
    )

    print(f"   video: {metadata.video_file_path}")
    print(f"   srt:   {metadata.subtitle_file_path}")
    assert metadata.lip_sync is not None, "composition metadata carries no lip-sync summary"
    print(f"   lip_sync: {metadata.lip_sync}")

    probe = ffprobe_summary(metadata.video_file_path)
    print(f"\n3. ffprobe: {probe['width']}x{probe['height']} {probe['codec_name']}/"
          f"{probe['pix_fmt']} {probe['avg_frame_rate']} {probe['duration']}s "
          f"audio={probe['audio_codec']}@{probe['audio_sample_rate']} ch={probe['audio_channels']}")
    assert probe["has_audio_stream"], "composition output has no audio stream"

    # Sample frames on speech and after it, on the muxed file itself.
    speech_end = dialogues[-1].end_time
    samples = {}
    for label, ts in (("during_speech_1", 0.6), ("during_speech_2", 3.6),
                      ("during_speech_3", 6.2), ("after_speech", speech_end + 0.5)):
        path = os.path.join(OUT, f"av_{label}_t{ts:05.2f}s.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(ts),
                        "-i", metadata.video_file_path, "-frames:v", "1", path], check=True)
        samples[label] = {"path": path, "timestamp": ts, **measure_frame(path)}
        print(f"   {label:18} t={ts:.2f}s black bands "
              f"T/B/L/R={samples[label]['top_black_band_ratio']:.3f}/"
              f"{samples[label]['bottom_black_band_ratio']:.3f}/"
              f"{samples[label]['left_black_band_ratio']:.3f}/"
              f"{samples[label]['right_black_band_ratio']:.3f}")

    write_json(os.path.join(OUT, "av_evidence.json"), {
        "report": report.to_dict(),
        "video_file_path": metadata.video_file_path,
        "subtitle_file_path": metadata.subtitle_file_path,
        "lip_sync": metadata.lip_sync,
        "ffprobe": probe,
        "dialogues": [
            {
                "speaker": d.character_id,
                "text": d.text,
                "audio_file": d.audio_file,
                "start_time": d.start_time,
                "end_time": d.end_time,
                "visemes": [v.model_dump(mode="json") for v in d.visemes],
            }
            for d in resolved.scenes[0].dialogues
        ],
        "frames": samples,
    })
    print(f"\nwrote {os.path.join(OUT, 'av_evidence.json')}")


if __name__ == "__main__":
    main()
