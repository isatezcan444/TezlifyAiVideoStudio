"""FFmpeg based video composition engine (Stage 4.5).

Pipeline:
1. Render every scene to a video-only clip with the existing Blender engine.
2. Join/crossfade clips according to the composition timeline.
3. Composite Turkish text/subtitle PNG overlays (Pillow).
4. Build one continuous AAC audio track from all dialogue files.
5. Validate the final MP4 with FFprobe.

Blender already renders each scene clip at the delivery format's own resolution
and aspect-aware camera framing, so step 2 is normally a straight concat. When a
clip does not match the target it is scaled to *fill* and cropped, never padded:
a black letterbox is a framing failure, and the fix belongs in the camera.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from typing import Callable, Dict, List, Optional

from tezlify_studio.application.ports.blender_animation_engine_port import (
    BlenderAnimationEnginePort,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    CompositionRenderException,
)
from tezlify_studio.domain.value_objects.camera_framing import profile_for_dimensions
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph, SceneResolution
from tezlify_studio.domain.value_objects.video_composition import (
    CompositionTimeline,
    CompositionTransition,
    TextAnchor,
    TextLayer,
    VideoComposition,
    build_composition_timeline,
    validate_composition_against_scene_ids,
)
from tezlify_studio.infrastructure.video.subtitle_builder import (
    build_subtitle_cues,
    probe_media_duration,
    write_srt,
)
from tezlify_studio.infrastructure.video.text_overlay_renderer import (
    OverlayImage,
    render_text_overlay,
)


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def build_cover_fit_filter(clip_width: int, clip_height: int, width: int, height: int) -> str:
    """Scale-to-fill then crop a mismatched clip; empty string when it already fits.

    The crop window is parked on the *source* format's safe centre instead of the
    geometric middle, so converting a portrait clip to landscape keeps the faces
    rather than the floor. This is the fallback path only: the real vertical
    composition comes from the camera solve in the render worker.
    """
    if clip_width <= 0 or clip_height <= 0:
        raise CompositionRenderException(
            f"Sahne klibinin çözünürlüğü okunamadı: {clip_width}x{clip_height}"
        )
    if clip_width == width and clip_height == height:
        return ""

    scale = max(width / clip_width, height / clip_height)
    scaled_width = math.ceil(clip_width * scale)
    scaled_height = math.ceil(clip_height * scale)

    excess_x = max(0, scaled_width - width)
    excess_y = max(0, scaled_height - height)
    left = int(round(excess_x * 0.5))
    top = int(round(excess_y * profile_for_dimensions(clip_width, clip_height).safe.center_y))

    return (
        f"scale={scaled_width}:{scaled_height}:force_original_aspect_ratio=disable,"
        f"crop={width}:{height}:{left}:{top}"
    )


class FFmpegCompositionEngine:
    def __init__(
        self,
        animation_engine: BlenderAnimationEnginePort,
        base_projects_dir: Optional[str] = None,
        keep_scene_clips: bool = False,
        ffmpeg_executable: str = "ffmpeg",
        ffprobe_executable: str = "ffprobe",
    ):
        self.animation_engine = animation_engine
        self.base_projects_dir = base_projects_dir or os.path.abspath("data/studio_projects")
        self.keep_scene_clips = keep_scene_clips
        self.ffmpeg = ffmpeg_executable
        self.ffprobe = ffprobe_executable

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render_composition(
        self,
        scene_graph: SceneGraph,
        composition: VideoComposition,
        project_id: str,
        job_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        engine_override: Optional[str] = None,
    ) -> RenderOutputMetadata:
        started = time.time()

        def report(percent: float, step: str) -> None:
            if progress_callback:
                try:
                    progress_callback(max(0.0, min(100.0, percent)), step)
                except Exception:
                    pass

        scene_ids = [scene.scene_id for scene in scene_graph.scenes]
        validate_composition_against_scene_ids(composition, scene_ids)

        proj_dir = os.path.join(self.base_projects_dir, project_id)
        renders_dir = os.path.join(proj_dir, "renders", job_id)
        work_dir = os.path.join(proj_dir, "compositions", job_id)
        overlays_dir = os.path.join(work_dir, "overlays")
        os.makedirs(renders_dir, exist_ok=True)
        os.makedirs(overlays_dir, exist_ok=True)

        scene_lookup = {scene.scene_id: scene for scene in scene_graph.scenes}
        scene_clips: Dict[str, str] = {}
        clip_durations: Dict[str, float] = {}
        clip_probe: Dict[str, dict] = {}
        rendered_scene_dirs: List[str] = []

        total_scenes = len(composition.scenes)
        report(3.0, f"Kompozisyon hazırlanıyor ({total_scenes} sahne)")

        # 1. Render each scene separately so a failure can be attributed to a
        # specific scene and the final edit can use precise clip durations.
        for index, comp_scene in enumerate(composition.scenes):
            scene_id = comp_scene.scene_id
            scene = scene_lookup[scene_id]
            scene_job_id = _safe_name(f"{job_id}_{index + 1:02d}_{scene_id}")
            base_percent = 3.0 + (index / total_scenes) * 62.0

            report(base_percent, f"Sahne {index + 1}/{total_scenes} render ediliyor: {scene_id}")

            single_graph = scene_graph.model_copy(deep=True)
            single_graph.scenes = [scene]
            single_graph.resolution = SceneResolution(
                width=composition.width,
                height=composition.height,
                aspect_ratio=composition.format.value,
                fps=composition.fps,
            )

            def scene_progress(pct: float, step: str, _base=base_percent) -> None:
                mapped = _base + (max(0.0, min(100.0, pct)) / 100.0) * (62.0 / total_scenes)
                report(mapped, f"{scene_id}: {step}")

            try:
                metadata = self.animation_engine.render_animation(
                    scene_graph=single_graph,
                    project_id=project_id,
                    job_id=scene_job_id,
                    progress_callback=scene_progress,
                    engine_override=engine_override,
                    include_audio=False,
                )
            except Exception as exc:
                raise CompositionRenderException(
                    f"Sahne '{scene_id}' render edilemedi: {exc}",
                    scene_id=scene_id,
                    details=str(exc),
                ) from exc

            clip_path = metadata.video_file_path
            if not clip_path or not os.path.isfile(clip_path) or os.path.getsize(clip_path) == 0:
                raise CompositionRenderException(
                    f"Sahne '{scene_id}' için geçerli bir video klip üretilemedi.",
                    scene_id=scene_id,
                )

            duration = probe_media_duration(clip_path)
            if duration <= 0:
                raise CompositionRenderException(
                    f"Sahne '{scene_id}' video süresi okunamadı.",
                    scene_id=scene_id,
                )

            clip_probe[scene_id] = self._probe_clip_geometry(clip_path, scene_id)

            scene_clips[scene_id] = clip_path
            clip_durations[scene_id] = duration
            rendered_scene_dirs.append(os.path.dirname(clip_path))
            report(
                base_percent + (62.0 / total_scenes),
                f"Sahne {index + 1}/{total_scenes} tamamlandı ({duration:.2f}s)",
            )

        # 2. Build the authoritative timeline from the actual clip durations.
        timeline = build_composition_timeline(composition, clip_durations)
        total_duration = timeline.total_duration_seconds
        if total_duration <= 0:
            raise CompositionRenderException("Kompozisyon toplam süresi hesaplanamadı.")

        report(68.0, "Sahne geçişleri FFmpeg ile birleştiriliyor")
        base_video_path = os.path.join(work_dir, "video_base.mp4")
        self._compose_base_video(
            composition=composition,
            timeline=timeline,
            scene_clips=scene_clips,
            clip_probe=clip_probe,
            output_path=base_video_path,
        )

        # 3. Text layers and subtitles.
        overlay_specs: List[dict] = []
        text_count = 0

        for index, layer in enumerate(composition.text_layers):
            if layer.start_time >= total_duration:
                continue
            end = min(layer.end_time, total_duration)
            if end <= layer.start_time:
                continue
            overlay = render_text_overlay(
                text=layer.text,
                output_path=os.path.join(overlays_dir, f"text_{index + 1:03d}.png"),
                frame_width=composition.width,
                frame_height=composition.height,
                anchor=layer.anchor,
                x_ratio=layer.x_ratio,
                y_ratio=layer.y_ratio,
                font_size=max(8, int(round(layer.font_size * composition.height / 1080.0))),
                color=layer.color,
                background_color=layer.background_color,
                background_opacity=layer.background_opacity,
                max_width_ratio=layer.max_width_ratio,
                bold=layer.bold,
            )
            overlay_specs.append(
                self._overlay_spec(
                    overlay,
                    layer.start_time,
                    end,
                    layer.fade_in_seconds,
                    layer.fade_out_seconds,
                )
            )
            text_count += 1

        subtitle_path: Optional[str] = None
        subtitle_cues = []
        if composition.subtitles.enabled:
            subtitle_cues = build_subtitle_cues(
                scene_graph=scene_graph,
                composition=composition,
                timeline=timeline,
                subtitle_settings=composition.subtitles,
            )

            if composition.subtitles.save_srt and subtitle_cues:
                subtitle_path = os.path.join(renders_dir, "subtitles.srt")
                write_srt(subtitle_cues, subtitle_path)

            if composition.subtitles.burn_in:
                for cue in subtitle_cues:
                    overlay = render_text_overlay(
                        text=cue.text,
                        output_path=os.path.join(overlays_dir, f"sub_{cue.index:04d}.png"),
                        frame_width=composition.width,
                        frame_height=composition.height,
                        anchor=TextAnchor.BOTTOM_CENTER,
                        x_ratio=0.5,
                        y_ratio=1.0 - composition.subtitles.margin_bottom_ratio,
                        font_size=max(12, int(round(
                            composition.subtitles.font_size * composition.height / 1080.0
                        ))),
                        color=composition.subtitles.color,
                        background_color=composition.subtitles.background_color,
                        background_opacity=composition.subtitles.background_opacity,
                        max_width_ratio=composition.subtitles.max_width_ratio,
                        bold=False,
                        stroke_width=max(2, int(composition.subtitles.font_size * composition.height / 1080.0) // 22),
                    )
                    overlay_specs.append(
                        self._overlay_spec(overlay, cue.start_seconds, cue.end_seconds, 0.0, 0.0)
                    )

        # 4. Continuous audio track from every dialogue in the edit.
        dialogue_audio: List[dict] = []
        for comp_scene in composition.scenes:
            entry = timeline.entry_for(comp_scene.scene_id)
            scene = scene_lookup[comp_scene.scene_id]
            for dialogue in sorted(scene.dialogues, key=lambda d: d.start_time):
                path = dialogue.audio_file or ""
                if not path or not os.path.isfile(path) or os.path.getsize(path) <= 500:
                    continue
                absolute_start = entry.start_time + dialogue.start_time
                if absolute_start >= total_duration:
                    continue
                dialogue_audio.append(
                    {
                        "path": path,
                        "delay_ms": max(0, int(round(absolute_start * 1000))),
                        "volume_db": composition.audio.dialogue_volume_db,
                        "character_id": dialogue.character_id,
                    }
                )

        music_path = composition.audio.music_file
        if music_path:
            music_path = os.path.abspath(os.path.expanduser(music_path))
            if not os.path.isfile(music_path):
                raise CompositionRenderException(
                    f"Arka plan müziği bulunamadı: {music_path}"
                )

        output_path = os.path.join(renders_dir, f"{job_id}.mp4")
        report(
            82.0,
            f"Metinler, altyazılar ve ses miksajı uygulanıyor "
            f"({len(overlay_specs)} katman, {len(dialogue_audio)} diyalog)",
        )
        self._compose_final_video(
            composition=composition,
            base_video_path=base_video_path,
            overlay_specs=overlay_specs,
            dialogue_audio=dialogue_audio,
            music_path=music_path,
            total_duration=total_duration,
            output_path=output_path,
        )

        # 5. Validate output.
        report(96.0, "Nihai MP4 FFprobe ile doğrulanıyor")
        probe = self._probe(output_path)
        video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None)
        format_info = probe.get("format", {})

        if not video_stream:
            raise CompositionRenderException("Nihai MP4 içinde video akışı bulunamadı.")
        if not audio_stream:
            raise CompositionRenderException("Nihai MP4 içinde ses akışı bulunamadı.")
        if video_stream.get("codec_name") != "h264":
            raise CompositionRenderException(
                f"Beklenmeyen video codec: {video_stream.get('codec_name')} (h264 bekleniyordu)."
            )
        if audio_stream.get("codec_name") != "aac":
            raise CompositionRenderException(
                f"Beklenmeyen ses codec: {audio_stream.get('codec_name')} (aac bekleniyordu)."
            )
        if int(video_stream.get("width", 0)) != composition.width or int(video_stream.get("height", 0)) != composition.height:
            raise CompositionRenderException(
                f"Çıktı çözünürlüğü beklenenden farklı: "
                f"{video_stream.get('width')}x{video_stream.get('height')} "
                f"(beklenen {composition.width}x{composition.height})."
            )

        actual_duration = float(format_info.get("duration", 0.0))
        if abs(actual_duration - total_duration) > 0.45:
            raise CompositionRenderException(
                f"Çıktı süresi beklenenden farklı: {actual_duration:.2f}s "
                f"(beklenen {total_duration:.2f}s)."
            )

        # 6. Persist composition/timeline metadata for reproducibility.
        manifest = {
            "composition": composition.model_dump(mode="json"),
            "timeline": {
                "total_duration_seconds": timeline.total_duration_seconds,
                "entries": [
                    {
                        "scene_id": entry.scene_id,
                        "order": entry.order,
                        "start_time": entry.start_time,
                        "end_time": entry.end_time,
                        "duration_seconds": entry.duration_seconds,
                        "transition": entry.transition.value,
                        "transition_duration_seconds": entry.transition_duration_seconds,
                    }
                    for entry in timeline.entries
                ],
            },
            "scene_clip_durations": clip_durations,
            "scene_clip_probe": clip_probe,
            "dialogue_audio": dialogue_audio,
            "subtitle_cues": [
                {
                    "index": cue.index,
                    "start_seconds": cue.start_seconds,
                    "end_seconds": cue.end_seconds,
                    "text": cue.text,
                    "scene_id": cue.scene_id,
                    "character_id": cue.character_id,
                }
                for cue in subtitle_cues
            ],
        }
        with open(os.path.join(work_dir, "composition_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)

        if not self.keep_scene_clips:
            for scene_dir in rendered_scene_dirs:
                try:
                    if os.path.abspath(scene_dir) != os.path.abspath(renders_dir):
                        shutil.rmtree(scene_dir, ignore_errors=True)
                except Exception:
                    pass

        report(100.0, "Video kompozisyonu tamamlandı")

        return RenderOutputMetadata(
            video_file_path=output_path,
            file_size_bytes=int(format_info.get("size", os.path.getsize(output_path))),
            duration_seconds=round(actual_duration, 3),
            width=int(video_stream.get("width", composition.width)),
            height=int(video_stream.get("height", composition.height)),
            fps=composition.fps,
            video_codec="h264",
            pixel_format=str(video_stream.get("pix_fmt", "yuv420p")),
            container="mp4",
            has_audio=True,
            audio_codec="aac",
            frame_count=int(round(actual_duration * composition.fps)),
            render_duration_seconds=round(time.time() - started, 2),
            engine="FFMPEG_COMPOSITION",
            composition_id=composition.id,
            composition_name=composition.name,
            format=composition.format.value,
            subtitle_file_path=subtitle_path,
            subtitle_cue_count=len(subtitle_cues),
            text_layer_count=text_count,
            transition_count=sum(
                1 for entry in timeline.entries if entry.transition != CompositionTransition.CUT
            ),
            scene_count=len(composition.scenes),
        )

    # ------------------------------------------------------------------
    # FFmpeg stages
    # ------------------------------------------------------------------
    def _compose_base_video(
        self,
        composition: VideoComposition,
        timeline: CompositionTimeline,
        scene_clips: Dict[str, str],
        clip_probe: Dict[str, dict],
        output_path: str,
    ) -> None:
        durations = [timeline.entry_for(item.scene_id).duration_seconds for item in composition.scenes]
        total_duration = timeline.total_duration_seconds
        fps = composition.fps
        width = composition.width
        height = composition.height

        cmd = [self.ffmpeg, "-y"]
        for item in composition.scenes:
            cmd.extend(["-i", scene_clips[item.scene_id]])

        filters: List[str] = []
        for index, item in enumerate(composition.scenes):
            duration = durations[index]
            geometry = clip_probe.get(item.scene_id, {})
            fit = build_cover_fit_filter(
                int(geometry.get("width", 0)),
                int(geometry.get("height", 0)),
                width,
                height,
            )
            chain = f"[{index}:v]fps={fps},"
            if fit:
                chain += fit + ","
            chain += "setsar=1,format=yuv420p,setpts=PTS-STARTPTS"
            if item.transition == CompositionTransition.FADE_IN:
                chain += f",fade=t=in:st=0:d={item.transition_duration_seconds}"
            elif item.transition == CompositionTransition.FADE_OUT:
                fade_start = max(0.0, duration - item.transition_duration_seconds)
                chain += f",fade=t=out:st={fade_start}:d={item.transition_duration_seconds}"
            chain += f"[v{index}]"
            filters.append(chain)

        current = "[v0]"
        current_duration = durations[0]
        for index in range(1, len(composition.scenes)):
            previous = composition.scenes[index - 1]
            if previous.transition == CompositionTransition.CROSSFADE:
                overlap = min(previous.transition_duration_seconds, current_duration, durations[index])
                offset = max(0.0, current_duration - overlap)
                filters.append(
                    f"{current}[v{index}]xfade=transition=fade:duration={overlap}:offset={offset}[x{index}]"
                )
                current = f"[x{index}]"
                current_duration = current_duration + durations[index] - overlap
            else:
                filters.append(f"{current}[v{index}]concat=n=2:v=1:a=0[x{index}]")
                current = f"[x{index}]"
                current_duration += durations[index]

        cmd.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                current,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-movflags",
                "+faststart",
                "-t",
                f"{total_duration:.3f}",
                output_path,
            ]
        )
        self._run(cmd, "Sahne geçişleri birleştirilemedi")

    def _compose_final_video(
        self,
        composition: VideoComposition,
        base_video_path: str,
        overlay_specs: List[dict],
        dialogue_audio: List[dict],
        music_path: Optional[str],
        total_duration: float,
        output_path: str,
    ) -> None:
        fps = composition.fps
        cmd = [self.ffmpeg, "-y", "-i", base_video_path]

        overlay_start = 1
        for spec in overlay_specs:
            display = max(0.05, spec["end"] - spec["start"])
            cmd.extend(
                [
                    "-loop",
                    "1",
                    "-framerate",
                    str(fps),
                    "-t",
                    f"{display:.3f}",
                    "-i",
                    spec["path"],
                ]
            )

        dialogue_start = overlay_start + len(overlay_specs)
        for item in dialogue_audio:
            cmd.extend(["-i", item["path"]])

        music_index = None
        if music_path:
            music_index = dialogue_start + len(dialogue_audio)
            cmd.extend(["-stream_loop", "-1", "-i", music_path])

        silence_index = dialogue_start + len(dialogue_audio) + (1 if music_path else 0)
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{total_duration:.3f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
            ]
        )

        filters: List[str] = [f"[0:v]format=yuv420p[basev]"]
        current_video = "[basev]"

        for index, spec in enumerate(overlay_specs):
            input_index = overlay_start + index
            chain = f"[{input_index}:v]format=rgba"
            if spec["fade_in"] > 0:
                chain += f",fade=t=in:st=0:d={spec['fade_in']}:alpha=1"
            if spec["fade_out"] > 0:
                fade_start = max(0.0, (spec["end"] - spec["start"]) - spec["fade_out"])
                chain += f",fade=t=out:st={fade_start}:d={spec['fade_out']}:alpha=1"
            chain += f",setpts=PTS-STARTPTS+{spec['start']}/TB[ov{index}]"
            filters.append(chain)
            filters.append(
                f"{current_video}[ov{index}]overlay={spec['x']}:{spec['y']}:"
                f"eof_action=pass:shortest=0[v{index}]"
            )
            current_video = f"[v{index}]"

        filters.append(
            f"[{silence_index}:a]atrim=duration={total_duration:.3f},asetpts=PTS-STARTPTS[abase]"
        )
        mix_labels = ["[abase]"]

        for index, item in enumerate(dialogue_audio):
            input_index = dialogue_start + index
            delay = item["delay_ms"]
            volume = item["volume_db"]
            filters.append(
                f"[{input_index}:a]aresample=44100,aformat=sample_rates=44100:channel_layouts=stereo,"
                f"volume={volume:g}dB,adelay={delay}|{delay}[ad{index}]"
            )
            mix_labels.append(f"[ad{index}]")

        if music_path and music_index is not None:
            filters.append(
                f"[{music_index}:a]atrim=0:{total_duration:.3f},"
                f"aresample=44100,aformat=sample_rates=44100:channel_layouts=stereo,"
                f"volume={composition.audio.music_volume_db:g}dB[amusic]"
            )
            mix_labels.append("[amusic]")

        if len(mix_labels) == 1:
            filters.append(f"{mix_labels[0]}anull[amixed]")
        else:
            filters.append(
                f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=longest:"
                f"dropout_transition=0:normalize=0[amixed]"
            )

        if composition.audio.limiter_enabled:
            filters.append(
                f"[amixed]alimiter=limit={composition.audio.limiter_limit}:attack=5:release=50[aout]"
            )
        else:
            filters.append("[amixed]anull[aout]")

        cmd.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                current_video,
                "-map",
                "[aout]",
                "-t",
                f"{total_duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                output_path,
            ]
        )
        self._run(cmd, "Metin, altyazı ve ses kompozisyonu oluşturulamadı")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _overlay_spec(
        overlay: OverlayImage,
        start: float,
        end: float,
        fade_in: float,
        fade_out: float,
    ) -> dict:
        duration = max(0.05, end - start)
        return {
            "path": overlay.path,
            "x": overlay.x,
            "y": overlay.y,
            "start": round(start, 3),
            "end": round(end, 3),
            "fade_in": min(fade_in, duration / 2.0),
            "fade_out": min(fade_out, duration / 2.0),
        }

    def _run(self, cmd: List[str], error_prefix: str) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise CompositionRenderException(
                f"{error_prefix}: {result.stderr[-1200:]}"
            )

    def _probe(self, path: str) -> dict:
        result = subprocess.run(
            [
                self.ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise CompositionRenderException(f"FFprobe doğrulaması başarısız: {result.stderr[-600:]}")
        try:
            return json.loads(result.stdout)
        except Exception as exc:
            raise CompositionRenderException(f"FFprobe çıktısı okunamadı: {exc}") from exc

    def _probe_clip_geometry(self, path: str, scene_id: str) -> dict:
        """Read a scene clip's real geometry so the fit decision is measured, not assumed."""
        probe = self._probe(path)
        stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None
        )
        if not stream:
            raise CompositionRenderException(
                f"Sahne '{scene_id}' klibinde video akışı bulunamadı.", scene_id=scene_id
            )
        return {
            "width": int(stream.get("width", 0)),
            "height": int(stream.get("height", 0)),
            "pix_fmt": str(stream.get("pix_fmt", "")),
            "codec": str(stream.get("codec_name", "")),
            "display_aspect_ratio": str(stream.get("display_aspect_ratio", "")),
            "sample_aspect_ratio": str(stream.get("sample_aspect_ratio", "")),
        }
