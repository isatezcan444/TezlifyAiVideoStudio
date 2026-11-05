import logging
from typing import Optional, Dict, Any

from tezlify_studio.application.ports.blender_animation_engine_port import (
    BlenderAnimationEnginePort,
)
from tezlify_studio.application.ports.composition_repository_port import (
    CompositionRepositoryPort,
)
from tezlify_studio.application.ports.voice_synthesizer_port import VoiceSynthesizerPort
from tezlify_studio.application.services.lip_sync_resolver import LipSyncResolver
from tezlify_studio.application.use_cases.synthesize_dialogue_audio_use_case import (
    SynthesizeDialogueAudioUseCase,
)
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidSceneGraphException,
    StudioProjectNotFoundException,
)
from tezlify_studio.domain.value_objects.video_composition import (
    VideoComposition,
    build_composition_timeline,
    validate_composition_against_scene_ids,
)
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.composition_repository_impl import (
    CompositionRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.render_job_repository_impl import (
    RenderJobRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.studio_project_repository_impl import (
    StudioProjectRepositoryImpl,
)

logger = logging.getLogger(__name__)


class ExecuteCompositionRenderUseCase:
    def __init__(
        self,
        composition_engine,
        voice_synthesizer: Optional[VoiceSynthesizerPort] = None,
        lip_sync_resolver: Optional[LipSyncResolver] = None,
    ):
        self.composition_engine = composition_engine
        self.voice_synthesizer = voice_synthesizer
        self.lip_sync_resolver = lip_sync_resolver

    def execute(
        self,
        job_id: str,
        project_id: str,
        composition_payload: Dict[str, Any],
        engine_override: Optional[str] = None,
        synthesize_voices: bool = True,
    ) -> None:
        db = SessionLocal()
        try:
            job_repo = RenderJobRepositoryImpl(db)
            project_repo = StudioProjectRepositoryImpl(db)

            job = job_repo.get_by_id(job_id)
            if not job:
                logger.error(f"Composition render job not found: {job_id}")
                return

            project = project_repo.get_by_id(project_id)
            if not project or not project.scene_graph:
                job.fail("Studio project or SceneGraph not found")
                job_repo.save(job)
                return

            job.start("Video composition engine starting")
            job_repo.save(job)

            project.transition_to(StudioProjectStatus.RENDERING)
            project_repo.save(project)

            # Synthesize missing/updated dialogue audio only when ElevenLabs is
            # actually configured. Never generate placeholder tones.
            if synthesize_voices and self.voice_synthesizer and self.voice_synthesizer.is_configured():
                try:
                    job.update_progress(6.0, "Synthesizing dialogue audio with ElevenLabs")
                    job_repo.save(job)

                    base_data_dir = getattr(
                        self.composition_engine,
                        "base_projects_dir",
                        settings.resolved_studio_projects_dir,
                    )
                    synth = SynthesizeDialogueAudioUseCase(self.voice_synthesizer)
                    updated_graph, _ = synth.execute(
                        scene_graph=project.scene_graph,
                        project_id=project_id,
                        audio_base_dir=base_data_dir,
                    )
                    project.update_scene_graph(updated_graph)
                    project_repo.save(project)
                except Exception as exc:
                    logger.warning(f"Voice synthesis error ({exc}). Continuing with existing audio.")

            composition = VideoComposition.model_validate(composition_payload)
            if composition.project_id != project_id:
                raise InvalidSceneGraphException("Kompozisyon proje kimliği uyuşmuyor.")
            validate_composition_against_scene_ids(
                composition,
                [scene.scene_id for scene in project.scene_graph.scenes],
            )

            # Stage 5.4: mouth timings come from the dialogue audio itself. Runs
            # after synthesis so it aligns what will actually be heard, and a
            # failure must never block a render that worked before this stage.
            scene_graph = project.scene_graph
            if self.lip_sync_resolver is not None:
                try:
                    job.update_progress(8.0, "Aligning dialogue audio for lip sync")
                    job_repo.save(job)
                    scene_graph, lip_sync_report = self.lip_sync_resolver.resolve(
                        project.scene_graph
                    )
                    if lip_sync_report.dialogues_aligned:
                        project.update_scene_graph(scene_graph)
                        project_repo.save(project)
                    logger.info(f"Lip sync report: {lip_sync_report.to_dict()}")
                except Exception as exc:
                    logger.warning(
                        f"Lip sync alignment failed ({exc}). Using legacy mouth animation."
                    )

            last_progress = [0.0]

            def on_progress(pct: float, step: str) -> None:
                if abs(pct - last_progress[0]) < 2.5 and pct < 100:
                    return
                last_progress[0] = pct
                try:
                    inner_db = SessionLocal()
                    try:
                        inner_repo = RenderJobRepositoryImpl(inner_db)
                        current = inner_repo.get_by_id(job_id)
                        if current:
                            current.update_progress(pct, step)
                            inner_repo.save(current)
                    finally:
                        inner_db.close()
                except Exception as exc:
                    logger.warning(f"Failed to update composition progress: {exc}")

            try:
                metadata = self.composition_engine.render_composition(
                    scene_graph=scene_graph,
                    composition=composition,
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

                logger.info(
                    f"Composition render {job_id} completed: {metadata.video_file_path}"
                )
            except Exception as exc:
                error = str(exc)
                logger.error(f"Composition render {job_id} failed: {error}")
                job = job_repo.get_by_id(job_id)
                if job:
                    job.fail(error)
                    job_repo.save(job)

                project = project_repo.get_by_id(project_id)
                if project:
                    project.transition_to(StudioProjectStatus.FAILED)
                    project_repo.save(project)
        finally:
            db.close()
