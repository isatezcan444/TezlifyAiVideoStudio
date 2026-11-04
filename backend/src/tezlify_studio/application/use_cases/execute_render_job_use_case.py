import logging
import subprocess
import threading
from typing import Optional

from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.render_job_repository_impl import (
    RenderJobRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.studio_project_repository_impl import (
    StudioProjectRepositoryImpl,
)
from tezlify_studio.application.ports.blender_animation_engine_port import BlenderAnimationEnginePort
from tezlify_studio.application.ports.voice_synthesizer_port import VoiceSynthesizerPort
from tezlify_studio.application.use_cases.synthesize_dialogue_audio_use_case import (
    SynthesizeDialogueAudioUseCase,
)
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.domain.enums.studio_status import RenderJobStatus, StudioProjectStatus
from tezlify_studio.domain.exceptions.studio_exceptions import StudioProjectNotFoundException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Render process registry
# ---------------------------------------------------------------------------
# Tracks active Blender/FFmpeg subprocesses keyed by render job id so that a
# cancellation request (or application shutdown) can terminate the exact
# subprocess started for that job -- and no other system process.
_ACTIVE_RENDER_PROCESSES: dict[str, subprocess.Popen] = {}
_PROCESSES_LOCK = threading.Lock()

# Job ids that have been cancelled. Checked by the worker so that a killed
# subprocess results in a CANCELLED job instead of a generic FAILED job.
_CANCELLED_JOB_IDS: set[str] = set()
_CANCELLED_LOCK = threading.Lock()


def register_render_process(job_id: str, proc: subprocess.Popen) -> None:
    """Register a subprocess belonging to a render job."""
    with _PROCESSES_LOCK:
        _ACTIVE_RENDER_PROCESSES[job_id] = proc


def deregister_render_process(job_id: str) -> None:
    """Remove a finished subprocess from the registry."""
    with _PROCESSES_LOCK:
        _ACTIVE_RENDER_PROCESSES.pop(job_id, None)


def cancel_render_process(job_id: str) -> bool:
    """Terminate the subprocess for a render job, if any.

    Returns True when a process was found and termination was attempted.
    Uses terminate() first, then kill() after a short grace period.
    Only the process started by this application for this job is touched.
    """
    with _PROCESSES_LOCK:
        proc = _ACTIVE_RENDER_PROCESSES.get(job_id)

    if proc is None:
        return False

    # Mark as cancelled so the worker records CANCELLED instead of FAILED.
    with _CANCELLED_LOCK:
        _CANCELLED_JOB_IDS.add(job_id)

    try:
        proc.terminate()
    except Exception:
        logger.warning(f"Failed to terminate render process for job {job_id}", exc_info=True)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            logger.warning(f"Failed to kill render process for job {job_id}", exc_info=True)

    return True


def is_job_cancelled(job_id: str) -> bool:
    with _CANCELLED_LOCK:
        return job_id in _CANCELLED_JOB_IDS


class ExecuteRenderJobUseCase:
    def __init__(
        self,
        animation_engine: BlenderAnimationEnginePort,
        voice_synthesizer: Optional[VoiceSynthesizerPort] = None,
    ):
        self.animation_engine = animation_engine
        self.voice_synthesizer = voice_synthesizer

    def execute(
        self,
        job_id: str,
        project_id: str,
        engine_override: Optional[str] = None,
        synthesize_voices: bool = True,
    ) -> None:
        db = SessionLocal()
        try:
            job_repo = RenderJobRepositoryImpl(db)
            project_repo = StudioProjectRepositoryImpl(db)

            job = job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"Render job not found: {job_id}")
                return

            project = project_repo.get_by_id(project_id)
            if not project or not project.scene_graph:
                job.fail("Studio project or SceneGraph not found")
                job_repo.save(job)
                return

            # If the job was cancelled before the worker started, honour it.
            if is_job_cancelled(job_id):
                job.cancel()
                job_repo.save(job)
                return

            job.start("Blender headless animation engine starting")
            job_repo.save(job)

            project.transition_to(StudioProjectStatus.RENDERING)
            project_repo.save(project)

            # Step: Synthesize dialogue speech with ElevenLabs if enabled and configured
            if synthesize_voices and self.voice_synthesizer and self.voice_synthesizer.is_configured():
                try:
                    job.update_progress(8.0, "Synthesizing dialogue audio with ElevenLabs")
                    job_repo.save(job)
                    base_data_dir = getattr(self.animation_engine, "base_projects_dir", "data/studio_projects")
                    synth_use_case = SynthesizeDialogueAudioUseCase(self.voice_synthesizer)
                    updated_sg, _ = synth_use_case.execute(
                        scene_graph=project.scene_graph,
                        project_id=project_id,
                        audio_base_dir=base_data_dir,
                    )
                    project.update_scene_graph(updated_sg)
                    project_repo.save(project)
                except Exception as ve:
                    logger.warning(f"Voice synthesis error ({ve}). Proceeding with animation.")

            last_update_pct = [5.0]

            def on_progress(pct: float, step: str):
                if abs(pct - last_update_pct[0]) >= 3.0 or pct >= 95.0:
                    last_update_pct[0] = pct
                    try:
                        db_inner = SessionLocal()
                        try:
                            inner_repo = RenderJobRepositoryImpl(db_inner)
                            j = inner_repo.get_by_id(job_id)
                            if j:
                                j.update_progress(pct, step)
                                inner_repo.save(j)
                        finally:
                            db_inner.close()
                    except Exception as pe:
                        logger.warning(f"Failed to update progress: {pe}")

            try:
                metadata = self.animation_engine.render_animation(
                    scene_graph=project.scene_graph,
                    project_id=project_id,
                    job_id=job_id,
                    progress_callback=on_progress,
                    engine_override=engine_override,
                )

                # If cancelled mid-render, do not overwrite with COMPLETED.
                if is_job_cancelled(job_id):
                    job.cancel()
                    job_repo.save(job)
                    project = project_repo.get_by_id(project_id)
                    if project:
                        project.transition_to(StudioProjectStatus.FAILED)
                        project_repo.save(project)
                    logger.info(f"Render job {job_id} was cancelled after completion.")
                    return

                job = job_repo.get_by_id(job_id)
                if job:
                    job.complete(video_path=metadata.video_file_path, metadata=metadata)
                    job_repo.save(job)

                project = project_repo.get_by_id(project_id)
                if project:
                    project.transition_to(StudioProjectStatus.COMPLETED)
                    project_repo.save(project)

                logger.info(f"Render job {job_id} successfully completed! Output: {metadata.video_file_path}")

            except Exception as re:
                err_msg = str(re)
                if is_job_cancelled(job_id):
                    logger.info(f"Render job {job_id} cancelled during execution.")
                    job = job_repo.get_by_id(job_id)
                    if job:
                        job.cancel()
                        job_repo.save(job)
                    project = project_repo.get_by_id(project_id)
                    if project:
                        project.transition_to(StudioProjectStatus.FAILED)
                        project_repo.save(project)
                    return

                logger.error(f"Render job {job_id} failed: {err_msg}")
                job = job_repo.get_by_id(job_id)
                if job:
                    job.fail(err_msg)
                    job_repo.save(job)

                project = project_repo.get_by_id(project_id)
                if project:
                    project.transition_to(StudioProjectStatus.FAILED)
                    project_repo.save(project)

        finally:
            db.close()
