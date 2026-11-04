import os
import sys
import json
import time
import shutil
import subprocess
from typing import Callable, Optional
from pathlib import Path

from tezlify_studio.application.ports.blender_animation_engine_port import BlenderAnimationEnginePort
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.domain.exceptions.studio_exceptions import BlenderRenderException

class BlenderAnimationEngineImpl(BlenderAnimationEnginePort):
    def __init__(
        self,
        blender_executable: Optional[str] = None,
        base_projects_dir: Optional[str] = None,
        assets_dir: Optional[str] = None,
        keep_frames: bool = False,
    ):
        self.blender_executable = blender_executable or self._find_blender()
        self.base_projects_dir = base_projects_dir or os.path.abspath("data/studio_projects")
        self.assets_dir = assets_dir or os.path.abspath("data/studio_assets")
        self.keep_frames = keep_frames

        # Path to the render worker script
        self.worker_script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "render_worker.py")
        )

    def _find_blender(self) -> str:
        # Standard macOS & Linux paths
        candidates = [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "blender",
            "/usr/bin/blender",
            "/usr/local/bin/blender",
        ]
        for c in candidates:
            if os.path.exists(c) or shutil.which(c):
                return c
        return "blender"

    def render_animation(
        self,
        scene_graph: SceneGraph,
        project_id: str,
        job_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        engine_override: Optional[str] = None,
        include_audio: bool = True,
    ) -> RenderOutputMetadata:
        start_time = time.time()

        def report(pct: float, step: str):
            if progress_callback:
                try:
                    progress_callback(pct, step)
                except Exception:
                    pass

        # 1. Prepare directory paths
        proj_dir = os.path.join(self.base_projects_dir, project_id)
        scenes_dir = os.path.join(proj_dir, "scenes")
        renders_dir = os.path.join(proj_dir, "renders", job_id)
        frames_dir = os.path.join(proj_dir, "frames", job_id)

        os.makedirs(scenes_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)
        os.makedirs(frames_dir, exist_ok=True)

        manifest_path = os.path.join(renders_dir, "render_manifest.json")
        result_path = os.path.join(renders_dir, "render_result.json")
        scene_save_path = os.path.join(scenes_dir, f"scene_{job_id}.blend")
        output_mp4_path = os.path.join(renders_dir, f"{job_id}.mp4")

        # 2. Write render manifest
        manifest_data = {
            "project_id": project_id,
            "job_id": job_id,
            "assets_dir": self.assets_dir,
            "frames_dir": frames_dir,
            "scene_save_path": scene_save_path,
            "result_path": result_path,
            "engine_override": engine_override or "BLENDER_WORKBENCH",
            "scene_graph": scene_graph.model_dump(),
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        report(5.0, "Launching Blender headless process")

        # 3. Launch Blender subprocess
        cmd = [
            self.blender_executable,
            "-b",
            "--python",
            self.worker_script,
            "--",
            manifest_path,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Stream stdout to capture progress
            stdout_lines = []
            if proc.stdout:
                for line in iter(proc.stdout.readline, ''):
                    stdout_lines.append(line)
                    stripped = line.strip()
                    if stripped.startswith("PROGRESS:"):
                        parts = stripped.split(":", 2)
                        if len(parts) >= 3:
                            try:
                                pct = float(parts[1])
                                step = parts[2]
                                report(pct, step)
                            except ValueError:
                                pass

            proc.wait(timeout=600)  # 10 min timeout
            stderr_out = proc.stderr.read() if proc.stderr else ""

            if proc.returncode != 0:
                err_snippet = "\n".join(stdout_lines[-30:]) + "\n" + stderr_out[-500:]
                raise BlenderRenderException(
                    f"Blender render worker failed with exit code {proc.returncode}",
                    details=err_snippet,
                )

        except subprocess.TimeoutExpired:
            proc.kill()
            raise BlenderRenderException("Blender rendering timed out (600s limit exceeded)")
        except Exception as e:
            if isinstance(e, BlenderRenderException):
                raise
            raise BlenderRenderException(f"Failed to execute Blender subprocess: {str(e)}")

        if not os.path.exists(result_path):
            raise BlenderRenderException("Blender worker finished without writing result summary")

        with open(result_path, "r", encoding="utf-8") as f:
            worker_result = json.load(f)

        total_frames = worker_result.get("total_frames", 0)
        fps = worker_result.get("fps", 30)
        width = worker_result.get("width", 1920)
        height = worker_result.get("height", 1080)

        # 4. Encode MP4 via FFmpeg (with synchronized audio tracks)
        report(88.0, "Encoding MP4 video with FFmpeg")

        # Collect dialogue audio files from the SceneGraph
        dialogue_audios = []
        cumulative_time = 0.0
        for scene in scene_graph.scenes:
            for dlg in scene.dialogues:
                if dlg.audio_file and os.path.exists(dlg.audio_file) and os.path.getsize(dlg.audio_file) > 500:
                    start_sec = cumulative_time + dlg.start_time
                    dialogue_audios.append((dlg.audio_file, int(round(start_sec * 1000))))
            cumulative_time += scene.duration_seconds

        if not include_audio:
            # Composition rendering needs video-only scene clips. The final
            # continuous audio track is built once by the composition engine.
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frames_dir, "frame_%04d.png"),
                "-an",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_mp4_path,
            ]
        elif dialogue_audios:
            report(88.0, f"Mixing {len(dialogue_audios)} dialogue audio tracks with FFmpeg")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frames_dir, "frame_%04d.png"),
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            ]
            for aud_path, _ in dialogue_audios:
                ffmpeg_cmd.extend(["-i", aud_path])

            filter_parts = ["[1:a]aresample=44100[base_a];"]
            mix_inputs = ["[base_a]"]

            for idx, (_, delay_ms) in enumerate(dialogue_audios, start=2):
                delay_ms = max(0, delay_ms)
                filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},aresample=44100[a{idx}];")
                mix_inputs.append(f"[a{idx}]")

            filter_parts.append(
                f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:dropout_transition=0:normalize=0[aout]"
            )
            filter_complex = " ".join(filter_parts)

            ffmpeg_cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                output_mp4_path,
            ])
        else:
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frames_dir, "frame_%04d.png"),
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-shortest",
                "-movflags", "+faststart",
                output_mp4_path,
            ]

        ff_res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if ff_res.returncode != 0 or not os.path.exists(output_mp4_path):
            # Fallback without audio track
            fallback_cmd = [
                "ffmpeg",
                "-y",
                "-framerate", str(fps),
                "-i", os.path.join(frames_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_mp4_path,
            ]
            fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True)
            if fb_res.returncode != 0 or not os.path.exists(output_mp4_path):
                raise BlenderRenderException(
                    f"FFmpeg encoding failed: {ff_res.stderr[-400:]}"
                )

        # 5. Technical Validation via FFprobe
        report(95.0, "Validating output MP4 technical parameters via FFprobe")

        probe_cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            output_mp4_path,
        ]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_res.returncode != 0:
            raise BlenderRenderException(f"FFprobe validation failed: {probe_res.stderr}")

        try:
            probe_data = json.loads(probe_res.stdout)
            format_info = probe_data.get("format", {})
            streams = probe_data.get("streams", [])

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
            if not video_stream:
                raise BlenderRenderException("FFprobe: Output MP4 contains no video stream")

            v_codec = video_stream.get("codec_name")
            v_pix_fmt = video_stream.get("pix_fmt")
            v_width = int(video_stream.get("width", 0))
            v_height = int(video_stream.get("height", 0))
            file_size = int(format_info.get("size", 0))
            duration = float(format_info.get("duration", 0.0))
            a_codec = audio_stream.get("codec_name", "aac") if audio_stream else "none"

            if file_size <= 0:
                raise BlenderRenderException(f"FFprobe: Generated MP4 file size is 0 bytes")
            if v_width != width or v_height != height:
                raise BlenderRenderException(
                    f"Resolution mismatch: expected {width}x{height}, got {v_width}x{v_height}"
                )
            if v_codec != "h264":
                raise BlenderRenderException(f"Codec mismatch: expected h264, got {v_codec}")
            if v_pix_fmt != "yuv420p":
                raise BlenderRenderException(f"Pixel format mismatch: expected yuv420p, got {v_pix_fmt}")

        except Exception as e:
            if isinstance(e, BlenderRenderException):
                raise
            raise BlenderRenderException(f"Failed to parse FFprobe output: {str(e)}")

        # 6. Cleanup temporary frames
        report(98.0, "Cleaning up temporary frame sequences")
        if not self.keep_frames and os.path.exists(frames_dir):
            try:
                shutil.rmtree(frames_dir)
            except Exception:
                pass

        render_duration = round(time.time() - start_time, 2)
        report(100.0, "Video render completed successfully")

        meta = RenderOutputMetadata(
            video_file_path=output_mp4_path,
            file_size_bytes=file_size,
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            video_codec=v_codec,
            pixel_format=v_pix_fmt,
            container="mp4",
            has_audio=bool(audio_stream),
            audio_codec=a_codec,
            frame_count=total_frames,
            render_duration_seconds=render_duration,
            engine=worker_result.get("engine", "BLENDER_WORKBENCH"),
        )

        # Save metadata to disk
        meta_file_path = os.path.join(renders_dir, "render_metadata.json")
        with open(meta_file_path, "w", encoding="utf-8") as f:
            json.dump(meta.model_dump(), f, indent=2)

        return meta
