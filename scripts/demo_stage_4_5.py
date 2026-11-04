#!/usr/bin/env python3
"""Stage 4.5 "Video Composition Studio" real demo.

Creates a three-scene Ali/Ayşe café story, renders each scene with the existing
Blender headless engine, generates dialogue audio, then uses the Stage 4.5
FFmpeg composition engine to produce:

* 16:9 (1920x1080) MP4
* 9:16 (1080x1920) MP4
* Turkish SRT subtitles

Voice policy
------------
The script prefers ElevenLabs when ``ELEVENLABS_API_KEY`` is configured. This
machine currently has no key, so the default ``auto`` mode falls back to the
macOS Turkish system voice and records that fact in the demo summary. It never
claims that fallback audio is ElevenLabs audio. Use ``--voice-source tone`` to
force test tones or ``--require-elevenlabs`` to fail instead of falling back.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend", "src"))

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
    AudioMixSettings,
    CompositionScene,
    CompositionTransition,
    SubtitleSettings,
    TextAnchor,
    TextLayer,
    VideoComposition,
    VideoFormat,
)
from tezlify_studio.infrastructure.ai.elevenlabs_client_impl import (  # noqa: E402
    ElevenLabsClientImpl,
)
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import (  # noqa: E402
    BlenderAnimationEngineImpl,
)
from tezlify_studio.infrastructure.video.ffmpeg_composition_engine import (  # noqa: E402
    FFmpegCompositionEngine,
)

PROJECT_ID = "demo_stage_4_5"
ALI_TEXT = "Merhaba Ayşe, bugün nasılsın? Kafeye gelirken seni düşündüm."
AYSE_TEXT = "İyiyim Ali, teşekkür ederim. Burada seninle kahve içmek çok güzel."
ALI_VOICE_ID = "IKne3meq5aSn9XLyUdCD"   # Charlie
AYSE_VOICE_ID = "cgSgspJ2msm6clMCkdW9"  # Jessica


@dataclass
class VoiceAsset:
    path: str
    duration_seconds: float
    source: str
    detail: str


def run(cmd: List[str], description: str) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{description} başarısız oldu.\nKomut: {' '.join(cmd)}\n"
            f"stderr:\n{result.stderr[-4000:]}"
        )
    return result


def probe_duration(path: str) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        f"Süre ölçülemedi: {path}",
    )
    return round(float(result.stdout.strip()), 3)


def synthesize_elevenlabs(text: str, output_path: str, voice_id: str) -> VoiceAsset:
    client = ElevenLabsClientImpl()
    result = client.synthesize_speech(text, voice_id, output_path)
    return VoiceAsset(
        path=output_path,
        duration_seconds=round(result.duration_seconds, 3),
        source="elevenlabs",
        detail=f"ElevenLabs voice={voice_id}, model={client.default_model}",
    )


def synthesize_macos_say(text: str, output_path: str, rate: int) -> VoiceAsset:
    if not shutil.which("say"):
        raise RuntimeError("macOS 'say' komutu bulunamadı.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    aiff_path = os.path.splitext(output_path)[0] + ".aiff"
    run(
        ["say", "-v", "Yelda", "-r", str(rate), "-o", aiff_path, text],
        "macOS Türkçe ses sentezi",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            aiff_path,
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            output_path,
        ],
        "Sistem sesi MP3'e dönüştürülemedi",
    )
    try:
        os.unlink(aiff_path)
    except OSError:
        pass
    return VoiceAsset(
        path=output_path,
        duration_seconds=probe_duration(output_path),
        source="macos_say",
        detail=f"macOS Yelda (tr_TR), rate={rate}",
    )


def synthesize_tone(text: str, output_path: str, frequency: int) -> VoiceAsset:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    duration = max(1.6, round(len(text) * 0.062, 2))
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration={duration}",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            output_path,
        ],
        "Test tonu üretilemedi",
    )
    return VoiceAsset(
        path=output_path,
        duration_seconds=probe_duration(output_path),
        source="test_tone",
        detail=f"{frequency} Hz sine tone — not speech",
    )


def make_voice_asset(
    text: str,
    output_path: str,
    voice_id: str,
    rate: int,
    frequency: int,
    voice_source: str,
    client: ElevenLabsClientImpl,
) -> VoiceAsset:
    if voice_source in ("auto", "elevenlabs"):
        if client.is_configured():
            try:
                return synthesize_elevenlabs(text, output_path, voice_id)
            except Exception as exc:
                if voice_source == "elevenlabs":
                    raise
                print(f"   [!] ElevenLabs başarısız ({exc}); sistem sesine geçiliyor.")
        elif voice_source == "elevenlabs":
            raise RuntimeError("ELEVENLABS_API_KEY yapılandırılmamış.")

    if voice_source in ("auto", "system"):
        try:
            return synthesize_macos_say(text, output_path, rate)
        except Exception as exc:
            if voice_source == "system":
                raise
            print(f"   [!] Sistem sesi başarısız ({exc}); test tonuna geçiliyor.")

    return synthesize_tone(text, output_path, frequency)


def build_scene_graph(
    ali_voice: VoiceAsset,
    ayse_voice: VoiceAsset,
) -> tuple[SceneGraph, float, float]:
    opening_duration = 3.2
    dialogue_lead_in = 0.8
    dialogue_gap = 0.65
    dialogue_tail = 1.0

    ali_start = dialogue_lead_in
    ali_end = round(ali_start + ali_voice.duration_seconds, 3)
    ayse_start = round(ali_end + dialogue_gap, 3)
    ayse_end = round(ayse_start + ayse_voice.duration_seconds, 3)
    dialogue_duration = round(ayse_end + dialogue_tail, 3)
    closing_duration = 3.2

    scene_graph = SceneGraph(
        schema_version="1.0",
        project_id=PROJECT_ID,
        title="Ali ve Ayşe — Kafe Buluşması",
        description="Stage 4.5 üç sahneli Türkçe kompozisyon demosu.",
        resolution=SceneResolution(width=1920, height=1080, fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali", voice_id=ALI_VOICE_ID),
            SceneCharacter(id="char_ayse", name="Ayşe", voice_id=AYSE_VOICE_ID),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_01_opening",
                sequence_order=1,
                duration_seconds=opening_duration,
                background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.WIDE_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ali",
                        position=[-0.85, 0.0, 0.0],
                        rotation_y=18.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.85, 0.0, 0.0],
                        rotation_y=-18.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                ],
                dialogues=[],
            ),
            StudioScene(
                scene_id="scene_02_dialogue",
                sequence_order=2,
                duration_seconds=dialogue_duration,
                background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ali",
                        position=[-0.75, 0.0, 0.0],
                        rotation_y=25.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.75, 0.0, 0.0],
                        rotation_y=-25.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                ],
                dialogues=[
                    SceneDialogue(
                        character_id="char_ali",
                        text=ALI_TEXT,
                        start_time=ali_start,
                        end_time=ali_end,
                        audio_file=ali_voice.path,
                    ),
                    SceneDialogue(
                        character_id="char_ayse",
                        text=AYSE_TEXT,
                        start_time=ayse_start,
                        end_time=ayse_end,
                        audio_file=ayse_voice.path,
                    ),
                ],
            ),
            StudioScene(
                scene_id="scene_03_closing",
                sequence_order=3,
                duration_seconds=closing_duration,
                background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.MEDIUM_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ali",
                        position=[-0.65, 0.0, 0.0],
                        rotation_y=15.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.65, 0.0, 0.0],
                        rotation_y=-15.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                ],
                dialogues=[],
            ),
        ],
    )
    return scene_graph, opening_duration, dialogue_duration


def build_composition(
    video_format: VideoFormat,
    opening_duration: float,
    dialogue_duration: float,
    closing_duration: float,
) -> VideoComposition:
    total = opening_duration + dialogue_duration + closing_duration - 1.2
    dialogue_scene_start = opening_duration - 0.6

    return VideoComposition(
        id=f"comp_{PROJECT_ID}",
        project_id=PROJECT_ID,
        name="Ali & Ayşe Kafe Kompozisyonu",
        format=video_format,
        fps=30,
        scenes=[
            CompositionScene(
                scene_id="scene_01_opening",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=0.6,
            ),
            CompositionScene(
                scene_id="scene_02_dialogue",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=0.6,
            ),
            CompositionScene(
                scene_id="scene_03_closing",
                transition=CompositionTransition.CUT,
                transition_duration_seconds=0.0,
            ),
        ],
        text_layers=[
            TextLayer(
                id="opening_title",
                text="Ali & Ayşe\nKafe Buluşması",
                start_time=0.25,
                end_time=2.4,
                anchor=TextAnchor.CENTER,
                x_ratio=0.5,
                y_ratio=0.22,
                font_size=76,
                color="#FFFFFF",
                background_color="#000000",
                background_opacity=0.28,
                fade_in_seconds=0.3,
                fade_out_seconds=0.35,
                max_width_ratio=0.86,
                bold=True,
            ),
            TextLayer(
                id="scene_title",
                text="Kafe Sohbeti",
                start_time=round(dialogue_scene_start + 0.35, 3),
                end_time=round(dialogue_scene_start + 2.3, 3),
                anchor=TextAnchor.TOP_CENTER,
                x_ratio=0.5,
                y_ratio=0.12,
                font_size=42,
                color="#FFF7E8",
                background_color="#3B2416",
                background_opacity=0.42,
                fade_in_seconds=0.25,
                fade_out_seconds=0.3,
                max_width_ratio=0.8,
                bold=True,
            ),
            TextLayer(
                id="closing_title",
                text="Tezlify AI Video Studio\nAşama 4.5",
                start_time=round(total - 2.8, 3),
                end_time=round(total - 0.2, 3),
                anchor=TextAnchor.BOTTOM_CENTER,
                x_ratio=0.5,
                y_ratio=0.9,
                font_size=46,
                color="#FFFFFF",
                background_color="#000000",
                background_opacity=0.5,
                fade_in_seconds=0.3,
                fade_out_seconds=0.3,
                max_width_ratio=0.84,
                bold=True,
            ),
        ],
        subtitles=SubtitleSettings(
            enabled=True,
            burn_in=True,
            save_srt=True,
            font_size=46,
            color="#FFFFFF",
            background_color="#000000",
            background_opacity=0.64,
            margin_bottom_ratio=0.075,
            max_width_ratio=0.84,
            max_chars_per_line=44,
        ),
        audio=AudioMixSettings(
            dialogue_volume_db=0.0,
            music_file=None,
            music_volume_db=-20.0,
            limiter_enabled=True,
            limiter_limit=0.95,
        ),
    )


def validate_output(metadata, expected_format: VideoFormat) -> Dict:
    probe = run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            metadata.video_file_path,
        ],
        "FFprobe doğrulaması",
    )
    data = json.loads(probe.stdout)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)

    expected_width, expected_height = {
        VideoFormat.LANDSCAPE_16_9: (1920, 1080),
        VideoFormat.PORTRAIT_9_16: (1080, 1920),
        VideoFormat.SQUARE_1_1: (1080, 1080),
    }[expected_format]

    checks = {
        "video_stream": bool(video),
        "audio_stream": bool(audio),
        "h264": video.get("codec_name") == "h264" if video else False,
        "aac": audio.get("codec_name") == "aac" if audio else False,
        "width": int(video.get("width", 0)) == expected_width if video else False,
        "height": int(video.get("height", 0)) == expected_height if video else False,
        "duration": abs(float(data["format"].get("duration", 0)) - metadata.duration_seconds) < 0.5,
        "subtitles": bool(metadata.subtitle_file_path and os.path.isfile(metadata.subtitle_file_path)),
    }
    if not all(checks.values()):
        raise RuntimeError(f"Çıktı doğrulaması başarısız: {checks}")

    # Full decode pass catches corrupt streams that ffprobe alone may miss.
    run(
        ["ffmpeg", "-v", "error", "-i", metadata.video_file_path, "-f", "null", "-"],
        "Tam decode doğrulaması",
    )

    return {
        "path": metadata.video_file_path,
        "duration_seconds": metadata.duration_seconds,
        "width": metadata.width,
        "height": metadata.height,
        "fps": metadata.fps,
        "video_codec": metadata.video_codec,
        "audio_codec": metadata.audio_codec,
        "file_size_bytes": metadata.file_size_bytes,
        "subtitle_file_path": metadata.subtitle_file_path,
        "subtitle_cue_count": metadata.subtitle_cue_count,
        "text_layer_count": metadata.text_layer_count,
        "transition_count": metadata.transition_count,
        "scene_count": metadata.scene_count,
        "checks": checks,
        "streams": {
            "video": {
                "codec": video.get("codec_name") if video else None,
                "pix_fmt": video.get("pix_fmt") if video else None,
                "profile": video.get("profile") if video else None,
            },
            "audio": {
                "codec": audio.get("codec_name") if audio else None,
                "sample_rate": audio.get("sample_rate") if audio else None,
                "channels": audio.get("channels") if audio else None,
            },
        },
    }


def run_demo(voice_source: str, formats: List[VideoFormat]) -> Dict:
    started = time.time()
    print("=" * 76)
    print("  TEZLIFY AI VIDEO STUDIO — AŞAMA 4.5 VİDEO KOMPOZİSYON DEMOSU")
    print("  Ali & Ayşe kafe buluşması · 3 sahne · Türkçe metin/altyazı · AAC")
    print("=" * 76)

    client = ElevenLabsClientImpl()
    if client.is_configured():
        print("[✓] ELEVENLABS_API_KEY bulundu; gerçek ElevenLabs sesi denenecek.")
    else:
        print("[!] ELEVENLABS_API_KEY bulunamadı.")
        print("    Gerçek ElevenLabs sesi üretilemez. Seçilen ses kaynağı:", voice_source)
        if voice_source == "auto":
            print("    'auto' modu macOS Türkçe sistem sesini (Yelda) kullanacak.")
        print("    Bu çıktı ElevenLabs çıktısı olarak raporlanmayacaktır.")

    audio_dir = os.path.join(ROOT_DIR, "data", "audio_cache", "stage_4_5")
    os.makedirs(audio_dir, exist_ok=True)
    ali_path = os.path.join(audio_dir, "ali_dialogue.mp3")
    ayse_path = os.path.join(audio_dir, "ayse_dialogue.mp3")

    print("\n1. Diyalog sesleri hazırlanıyor...")
    ali_voice = make_voice_asset(
        ALI_TEXT,
        ali_path,
        ALI_VOICE_ID,
        rate=170,
        frequency=320,
        voice_source=voice_source,
        client=client,
    )
    ayse_voice = make_voice_asset(
        AYSE_TEXT,
        ayse_path,
        AYSE_VOICE_ID,
        rate=185,
        frequency=580,
        voice_source=voice_source,
        client=client,
    )
    print(f"   Ali : {ali_voice.duration_seconds:.2f}s · {ali_voice.source} · {ali_voice.detail}")
    print(f"   Ayşe: {ayse_voice.duration_seconds:.2f}s · {ayse_voice.source} · {ayse_voice.detail}")

    scene_graph, opening_duration, dialogue_duration = build_scene_graph(ali_voice, ayse_voice)
    closing_duration = scene_graph.scenes[2].duration_seconds
    base_total = opening_duration + dialogue_duration + closing_duration - 1.2
    print(f"\n2. SceneGraph hazır: 3 sahne, tahmini süre {base_total:.2f}s")
    print(f"   Açılış: {opening_duration:.2f}s · Diyalog: {dialogue_duration:.2f}s · Kapanış: {closing_duration:.2f}s")

    engine = BlenderAnimationEngineImpl()
    composition_engine = FFmpegCompositionEngine(animation_engine=engine)
    run_stamp = time.strftime("%Y%m%d_%H%M%S")
    output_records: Dict[str, Dict] = {}

    for video_format in formats:
        label = video_format.value.replace(":", "x")
        job_id = f"job_{run_stamp}_{label}"
        composition = build_composition(
            video_format,
            opening_duration,
            dialogue_duration,
            closing_duration,
        )

        print("\n" + "-" * 76)
        print(f"3. {video_format.value} kompozisyon render ediliyor ({job_id})")
        print("-" * 76)

        def on_progress(percent: float, step: str) -> None:
            if percent >= 100 or abs(percent - round(percent)) < 0.01:
                print(f"   [{percent:6.1f}%] {step}")

        metadata = composition_engine.render_composition(
            scene_graph=scene_graph,
            composition=composition,
            project_id=PROJECT_ID,
            job_id=job_id,
            progress_callback=on_progress,
            engine_override="BLENDER_WORKBENCH",
        )
        record = validate_output(metadata, video_format)
        record["format"] = video_format.value
        record["job_id"] = job_id
        output_records[video_format.value] = record

        print(f"   [✓] MP4: {record['path']}")
        print(
            f"   [✓] {record['width']}x{record['height']} · {record['duration_seconds']:.2f}s · "
            f"{record['file_size_bytes'] / (1024 * 1024):.2f} MB · h264/aac"
        )
        print(f"   [✓] SRT: {record['subtitle_file_path']} ({record['subtitle_cue_count']} cue)")

    summary_path = os.path.join(
        ROOT_DIR, "data", "studio_projects", PROJECT_ID, "demo_stage_4_5_summary.json"
    )
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    summary = {
        "stage": "4.5",
        "project_id": PROJECT_ID,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wall_clock_seconds": round(time.time() - started, 2),
        "voice_source": {
            "ali": asdict(ali_voice),
            "ayse": asdict(ayse_voice),
            "elevenlabs_configured": client.is_configured(),
        },
        "scene_graph": scene_graph.model_dump(mode="json"),
        "outputs": output_records,
    }
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 76)
    print("  DEMO TAMAMLANDI")
    print(f"  Özet: {summary_path}")
    if all(record.get("checks", {}).get("subtitles") for record in output_records.values()):
        print("  Türkçe SRT altyazıları üretildi.")
    print("  Ses kaynağı: " + ", ".join(
        sorted({ali_voice.source, ayse_voice.source})
    ))
    if not client.is_configured():
        print("  NOT: Bu demo gerçek ElevenLabs sesi içermiyor; ses kaynağı yukarıda açıkça belirtilmiştir.")
    print("=" * 76)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 4.5 three-scene composition demo")
    parser.add_argument(
        "--voice-source",
        choices=["auto", "elevenlabs", "system", "tone"],
        default="auto",
        help="auto: ElevenLabs if configured, otherwise macOS Turkish TTS",
    )
    parser.add_argument(
        "--require-elevenlabs",
        action="store_true",
        help="fail instead of falling back when ElevenLabs is unavailable",
    )
    parser.add_argument(
        "--formats",
        default="16:9,9:16",
        help="comma separated formats: 16:9, 9:16, 1:1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    voice_source = args.voice_source
    if args.require_elevenlabs:
        voice_source = "elevenlabs"

    formats = []
    for raw in args.formats.split(","):
        value = raw.strip()
        if value:
            formats.append(VideoFormat(value))
    if not formats:
        raise SystemExit("En az bir format belirtin.")

    run_demo(voice_source, formats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
