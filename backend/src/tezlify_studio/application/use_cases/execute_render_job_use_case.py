import logging
from typing import Optional
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.render_job_repository_impl import RenderJobRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.studio_project_repository_impl import StudioProjectRepositoryImpl
from tezlify_studio.application.ports.blender_animation_engine_port import BlenderAnimationEnginePort
from tezlify_studio.application.ports.voice_synthesizer_port import VoiceSynthesizerPort
from tezlify_studio.application.use_cases.synthesize_dialogue_audio_use_case import SynthesizeDialogueAudioUseCase
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus

logger = logging.getLogger(__name__)

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
