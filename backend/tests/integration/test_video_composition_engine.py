import json
import os
import re
import subprocess
import tempfile
from typing import Optional

import pytest
from PIL import Image

from tezlify_studio.domain.exceptions.studio_exceptions import (
    CompositionRenderException,
)
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.domain.value_objects.scene_graph import (
    CharacterPlacement,
    SceneCharacter,
    SceneDialogue,
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.domain.value_objects.video_composition import (
    CompositionScene,
    CompositionTransition,
    SubtitleSettings,
    TextAnchor,
    TextLayer,
    VideoComposition,
    VideoFormat,
    build_composition_timeline,
)
from tezlify_studio.infrastructure.video.ffmpeg_composition_engine import (
    FFmpegCompositionEngine,
    build_cover_fit_filter,
)
from tezlify_studio.infrastructure.video.subtitle_builder import (
    build_subtitle_cues,
    write_srt,
)
from tezlify_studio.infrastructure.video.text_overlay_renderer import (
    render_text_overlay,
)


class FakeClipEngine:
    """Produces real MP4 clips with FFmpeg; keeps composition tests fast."""

    def __init__(self, work_dir: str, fail_scene_id: Optional[str] = None):
        self.work_dir = work_dir
        self.fail_scene_id = fail_scene_id

    def render_animation(
        self,
        scene_graph,
        project_id,
        job_id,
        progress_callback=None,
        engine_override=None,
        include_audio=True,
    ):
        scene = scene_graph.scenes[0]
        if self.fail_scene_id and scene.scene_id == self.fail_scene_id:
            raise RuntimeError(f"forced failure for {scene.scene_id}")

        width = scene_graph.resolution.width
        height = scene_graph.resolution.height
        fps = scene_graph.resolution.fps
        duration = scene.duration_seconds
        colors = {"s1": "0x1e3a8a", "s2": "0x7c2d12", "s3": "0x14532d"}
        color = colors.get(scene.scene_id, "0x334155")
        output = os.path.join(self.work_dir, f"{job_id}.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c={color}:s={width}x{height}:r={fps}:d={duration}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-an",
                output,
            ],
            check=True,
            capture_output=True,
        )
        if progress_callback:
            progress_callback(100.0, "fake clip complete")
        return RenderOutputMetadata(
            video_file_path=output,
            file_size_bytes=os.path.getsize(output),
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            has_audio=False,
            audio_codec="none",
        )


def make_audio(path: str, duration: float = 0.6, freq: int = 440) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency={freq}:duration={duration}",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            path,
        ],
        check=True,
        capture_output=True,
    )


def make_scene_graph(audio_dir: str, width: int = 640, height: int = 360) -> SceneGraph:
    s1_audio = os.path.join(audio_dir, "s1.mp3")
    s2_audio = os.path.join(audio_dir, "s2.mp3")
    make_audio(s1_audio, duration=0.5)
    make_audio(s2_audio, duration=0.5, freq=660)

    return SceneGraph(
        project_id="proj_composition_test",
        title="Kompozisyon Testi ŞİĞÜÖÇ",
        resolution=SceneResolution(width=width, height=height, fps=30),
        characters=[SceneCharacter(id="char_ali", name="Ali")],
        scenes=[
            StudioScene(
                scene_id="s1",
                sequence_order=1,
                duration_seconds=1.2,
                character_placements=[CharacterPlacement(character_id="char_ali")],
                dialogues=[
                    SceneDialogue(
                        character_id="char_ali",
                        start_time=0.4,
                        end_time=0.9,
                        text="Merhaba Ayşe, bugün nasılsın?",
                        audio_file=s1_audio,
                    )
                ],
            ),
            StudioScene(
                scene_id="s2",
                sequence_order=2,
                duration_seconds=1.2,
                character_placements=[CharacterPlacement(character_id="char_ali")],
                dialogues=[
                    SceneDialogue(
                        character_id="char_ali",
                        start_time=0.0,
                        end_time=0.5,
                        text="İyiyim Ali, teşekkür ederim.",
                        audio_file=s2_audio,
                    )
                ],
            ),
            StudioScene(
                scene_id="s3",
                sequence_order=3,
                duration_seconds=1.0,
                character_placements=[CharacterPlacement(character_id="char_ali")],
            ),
        ],
    )


def make_composition(video_format: VideoFormat = VideoFormat.LANDSCAPE_16_9) -> VideoComposition:
    return VideoComposition(
        id="comp_test",
        project_id="proj_composition_test",
        name="Test Kompozisyonu",
        format=video_format,
        fps=30,
        scenes=[
            CompositionScene(
                scene_id="s1",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=0.4,
            ),
            CompositionScene(
                scene_id="s2",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=0.4,
            ),
            CompositionScene(
                scene_id="s3",
                transition=CompositionTransition.FADE_OUT,
                transition_duration_seconds=0.3,
            ),
        ],
        text_layers=[
            TextLayer(
                id="opening",
                text="Ali & Ayşe — Kafe Sohbeti",
                start_time=0.1,
                end_time=1.0,
                anchor=TextAnchor.TOP_CENTER,
                y_ratio=0.12,
                font_size=52,
            )
        ],
        subtitles=SubtitleSettings(font_size=32, max_chars_per_line=30),
    )


def probe_streams(path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def silence_intervals(path: str) -> list:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", path,
            "-af", "silencedetect=noise=-35dB:d=0.08",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([0-9.]+)", result.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([0-9.]+)", result.stderr)]
    intervals = []
    for idx, start in enumerate(starts):
        end = ends[idx] if idx < len(ends) else 999.0
        intervals.append((start, end))
    return intervals


@pytest.mark.parametrize(
    "video_format,expected_size",
    [
        (VideoFormat.LANDSCAPE_16_9, (1920, 1080)),
        (VideoFormat.PORTRAIT_9_16, (1080, 1920)),
        (VideoFormat.SQUARE_1_1, (1080, 1080)),
    ],
)
def test_composition_engine_outputs_all_delivery_formats(video_format, expected_size):
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition(video_format)
        engine = FFmpegCompositionEngine(
            FakeClipEngine(tmp),
            base_projects_dir=tmp,
            keep_scene_clips=True,
        )

        metadata = engine.render_composition(
            scene_graph=graph,
            composition=composition,
            project_id="proj_composition_test",
            job_id=f"job_{video_format.value.replace(':', 'x')}",
        )

        assert (metadata.width, metadata.height) == expected_size
        assert metadata.has_audio is True
        assert metadata.audio_codec == "aac"
        assert metadata.video_codec == "h264"
        assert metadata.duration_seconds == pytest.approx(2.6, abs=0.35)
        assert os.path.getsize(metadata.video_file_path) > 10_000

        streams = probe_streams(metadata.video_file_path)
        video = next(s for s in streams["streams"] if s["codec_type"] == "video")
        audio = next(s for s in streams["streams"] if s["codec_type"] == "audio")
        assert (video["width"], video["height"]) == expected_size
        assert video["codec_name"] == "h264"
        assert audio["codec_name"] == "aac"
        assert int(audio["sample_rate"]) == 44100


def test_composition_engine_text_and_srt_output():
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition()
        engine = FFmpegCompositionEngine(
            FakeClipEngine(tmp),
            base_projects_dir=tmp,
            keep_scene_clips=True,
        )
        metadata = engine.render_composition(
            scene_graph=graph,
            composition=composition,
            project_id="proj_composition_test",
            job_id="job_text_srt",
        )

        assert metadata.text_layer_count == 1
        assert metadata.subtitle_cue_count == 2
        assert metadata.subtitle_file_path is not None
        assert os.path.isfile(metadata.subtitle_file_path)

        srt = open(metadata.subtitle_file_path, encoding="utf-8").read()
        assert "Merhaba Ayşe, bugün nasılsın?" in srt
        assert "İyiyim Ali, teşekkür ederim." in srt
        assert "00:00:00,400 --> 00:00:00,900" in srt

        overlay_png = os.path.join(
            tmp, "proj_composition_test", "compositions", "job_text_srt", "overlays", "text_001.png"
        )
        assert os.path.isfile(overlay_png)
        with Image.open(overlay_png) as image:
            assert image.mode == "RGBA"
            assert image.width > 20 and image.height > 20


def test_composition_engine_keeps_audio_continuous_across_crossfade():
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition()
        engine = FFmpegCompositionEngine(
            FakeClipEngine(tmp),
            base_projects_dir=tmp,
            keep_scene_clips=True,
        )
        metadata = engine.render_composition(
            scene_graph=graph,
            composition=composition,
            project_id="proj_composition_test",
            job_id="job_sync",
        )

        intervals = silence_intervals(metadata.video_file_path)
        # Speech spans 0.4s -> 1.3s continuously (second scene starts at 0.8s).
        gaps_inside_speech = [
            (start, end)
            for start, end in intervals
            if start < 1.25 and end > 0.45 and (end - start) > 0.05
        ]
        assert gaps_inside_speech == []

        # First audio must start near the scheduled 0.4s, not at 0 or late.
        first_speech = next((end for start, end in intervals if end < 0.8), None)
        assert first_speech is not None
        assert first_speech == pytest.approx(0.4, abs=0.12)


def test_composition_engine_reports_failing_scene_and_can_retry():
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition()

        failing = FFmpegCompositionEngine(
            FakeClipEngine(tmp, fail_scene_id="s2"),
            base_projects_dir=tmp,
        )
        with pytest.raises(CompositionRenderException) as error:
            failing.render_composition(
                scene_graph=graph,
                composition=composition,
                project_id="proj_composition_test",
                job_id="job_fail",
            )
        assert error.value.scene_id == "s2"
        assert "s2" in str(error.value)

        recovered = FFmpegCompositionEngine(
            FakeClipEngine(tmp),
            base_projects_dir=tmp,
            keep_scene_clips=True,
        )
        metadata = recovered.render_composition(
            scene_graph=graph,
            composition=composition,
            project_id="proj_composition_test",
            job_id="job_retry",
        )
        assert os.path.isfile(metadata.video_file_path)
        assert metadata.has_audio is True


def test_subtitle_timing_uses_measured_audio_duration():
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition()
        durations = {scene.scene_id: scene.duration_seconds for scene in graph.scenes}
        timeline = build_composition_timeline(composition, durations)

        cues = build_subtitle_cues(
            scene_graph=graph,
            composition=composition,
            timeline=timeline,
            subtitle_settings=composition.subtitles,
        )
        # Scene 2 starts at 0.8s due to the 0.4s crossfade.
        assert cues[1].start_seconds == pytest.approx(0.8)
        assert cues[1].end_seconds - cues[1].start_seconds == pytest.approx(0.5, abs=0.02)

        srt_path = os.path.join(tmp, "out.srt")
        write_srt(cues, srt_path)
        content = open(srt_path, encoding="utf-8").read()
        assert "00:00:00,800 --> 00:00:01,300" in content
        assert "ŞİĞÜÖÇ" not in content  # not in the spoken lines


def test_text_overlay_supports_turkish_glyphs_and_transparency():
    with tempfile.TemporaryDirectory() as tmp:
        output = os.path.join(tmp, "turkish.png")
        overlay = render_text_overlay(
            text="ŞİĞÜÖÇ ıİ — Türkçe Başlık",
            output_path=output,
            frame_width=1080,
            frame_height=1920,
            anchor=TextAnchor.BOTTOM_CENTER,
            y_ratio=0.9,
            font_size=64,
            background_opacity=0.6,
        )
        assert os.path.isfile(output)
        assert overlay.x >= 0 and overlay.y >= 0
        with Image.open(output) as image:
            alpha = image.getchannel("A")
            assert alpha.getbbox() is not None
            assert image.width <= 1080
            assert image.height < 1920


# ----------------------------------------------------------------------
# Stage 5.3 — a mismatched clip must be cropped, never letterboxed
# ----------------------------------------------------------------------

def _edge_black_band_ratios(path: str) -> dict:
    """Share of the frame taken by a fully black band touching each edge."""
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

    def run(start: int, stop: int, step: int, is_black) -> int:
        count = 0
        index = start
        while (step > 0 and index < stop) or (step < 0 and index > stop):
            if not is_black(index):
                break
            count += 1
            index += step
        return count

    return {
        "top": run(0, height, 1, row_black) / height,
        "bottom": run(height - 1, -1, -1, row_black) / height,
        "left": run(0, width, 1, col_black) / width,
        "right": run(width - 1, -1, -1, col_black) / width,
    }


class LegacyLandscapeClipEngine:
    """Emits 16:9 clips no matter what delivery format was asked for.

    This is the shape of the old bug: a scene rendered once and then letterboxed
    into a 9:16 file. The engine must fill the frame instead.
    """

    def __init__(self, work_dir: str, clip_width: int = 1920, clip_height: int = 1080):
        self.work_dir = work_dir
        self.clip_width = clip_width
        self.clip_height = clip_height

    def render_animation(
        self,
        scene_graph,
        project_id,
        job_id,
        progress_callback=None,
        engine_override=None,
        include_audio=True,
    ):
        scene = scene_graph.scenes[0]
        duration = scene.duration_seconds
        output = os.path.join(self.work_dir, f"{job_id}.mp4")
        # Colour-coded per scene so a crop of the wrong clip is visible in the result.
        colors = {"s1": "0x1e3a8a", "s2": "0x7c2d12", "s3": "0x14532d"}
        color = colors.get(scene.scene_id, "0x334155")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c={color}:s={self.clip_width}x{self.clip_height}:r=30:d={duration}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-an",
                output,
            ],
            check=True,
            capture_output=True,
        )
        return RenderOutputMetadata(
            video_file_path=output,
            file_size_bytes=os.path.getsize(output),
            duration_seconds=duration,
            width=self.clip_width,
            height=self.clip_height,
            fps=30,
            has_audio=False,
            audio_codec="none",
        )


def test_cover_fit_filter_passes_through_a_matching_clip():
    assert build_cover_fit_filter(1080, 1920, 1080, 1920) == ""
    assert build_cover_fit_filter(1920, 1080, 1920, 1080) == ""


def test_cover_fit_filter_crops_rather_than_pads():
    chain = build_cover_fit_filter(1920, 1080, 1080, 1920)
    assert chain
    assert "pad=" not in chain, "black padding is the defect this stage removes"
    assert "color=black" not in chain
    assert "crop=1080:1920:" in chain
    # The scaled source must be at least as large as the crop window on both axes.
    scaled = re.search(r"scale=(\d+):(\d+)", chain)
    assert int(scaled.group(1)) >= 1080 and int(scaled.group(2)) >= 1920


def test_cover_fit_filter_offsets_the_crop_by_the_source_safe_area():
    """A portrait clip flattened to landscape keeps faces, not the floor."""
    portrait_to_landscape = build_cover_fit_filter(1080, 1920, 1920, 1080)
    landscape_to_portrait = build_cover_fit_filter(1920, 1080, 1080, 1920)

    top_portrait = int(re.search(r"crop=\d+:\d+:\d+:(\d+)", portrait_to_landscape).group(1))
    excess = 1920 * (1920 / 1080) - 1080  # vertical room left after filling 1920 wide
    assert 0 < top_portrait < excess, "crop window must sit inside the scaled source"
    assert top_portrait < excess / 2, "portrait safe centre is above the middle row"

    # Cropping a landscape clip to portrait only removes width, so it stays centred.
    left = int(re.search(r"crop=\d+:\d+:(\d+):(\d+)", landscape_to_portrait).groups()[0])
    top = int(re.search(r"crop=\d+:\d+:(\d+):(\d+)", landscape_to_portrait).groups()[1])
    assert top == 0
    assert left > 0


def test_cover_fit_filter_rejects_an_unreadable_clip():
    with pytest.raises(CompositionRenderException):
        build_cover_fit_filter(0, 0, 1080, 1920)


@pytest.mark.parametrize(
    "video_format,expected_size",
    [
        (VideoFormat.PORTRAIT_9_16, (1080, 1920)),
        (VideoFormat.LANDSCAPE_16_9, (1920, 1080)),
        (VideoFormat.SQUARE_1_1, (1080, 1080)),
    ],
)
def test_mismatched_scene_clips_are_filled_not_letterboxed(video_format, expected_size):
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition(video_format)
        engine = FFmpegCompositionEngine(
            LegacyLandscapeClipEngine(tmp),
            base_projects_dir=tmp,
            keep_scene_clips=True,
        )

        metadata = engine.render_composition(
            scene_graph=graph,
            composition=composition,
            project_id="proj_cover_fit",
            job_id=f"job_cover_{video_format.value.replace(':', 'x')}",
        )

        assert (metadata.width, metadata.height) == expected_size

        probe = probe_streams(metadata.video_file_path)
        video = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"]) == expected_size
        assert video["pix_fmt"] == "yuv420p"

        frame = os.path.join(tmp, "sample.png")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "0.6", "-i", metadata.video_file_path,
             "-frames:v", "1", frame],
            check=True,
            capture_output=True,
        )
        bands = _edge_black_band_ratios(frame)
        assert bands == {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0}, (
            f"{video_format.value} output carries a black letterbox band: {bands}"
        )


def test_composition_manifest_records_the_measured_clip_geometry():
    with tempfile.TemporaryDirectory() as tmp:
        graph = make_scene_graph(tmp)
        composition = make_composition(VideoFormat.PORTRAIT_9_16)
        engine = FFmpegCompositionEngine(
            LegacyLandscapeClipEngine(tmp),
            base_projects_dir=tmp,
            keep_scene_clips=True,
        )
        metadata = engine.render_composition(
            scene_graph=graph,
            composition=composition,
            project_id="proj_probe_record",
            job_id="job_probe_record",
        )

        manifest_path = os.path.join(
            tmp, "proj_probe_record", "compositions", "job_probe_record",
            "composition_manifest.json",
        )
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        assert manifest["composition"]["format"] == "9:16"
        assert manifest["scene_clip_probe"]["s1"]["width"] == 1920
        assert manifest["scene_clip_probe"]["s1"]["height"] == 1080
        assert manifest["scene_clip_probe"]["s1"]["pix_fmt"] == "yuv420p"
        assert os.path.getsize(metadata.video_file_path) > 10_000
