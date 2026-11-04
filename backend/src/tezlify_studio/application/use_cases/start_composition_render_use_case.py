import threading
import uuid
from typing import Any, Dict, Optional

from tezlify_studio.application.dto.composition_dto import (
    StartCompositionRenderRequestDTO,
)
from tezlify_studio.application.dto.render_dto import RenderJobDTO
from tezlify_studio.application.ports.composition_repository_port import (
    CompositionRepositoryPort,
)
from tezlify_studio.application.ports.render_job_repository_port import (
    RenderJobRepositoryPort,
)
from tezlify_studio.application.ports.studio_project_repository_port import (
    StudioProjectRepositoryPort,
)
from tezlify_studio.application.services.composition_factory import (
    default_composition_for,
    timeline_for,
)
from tezlify_studio.application.use_cases.execute_composition_render_use_case import (
    ExecuteCompositionRenderUseCase,
)
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import (
    RenderJobStatus,
    StudioProjectStatus,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidCompositionException,
    InvalidRenderStateException,
    StudioProjectNotFoundException,
)
from tezlify_studio.domain.value_objects.video_composition import (
    VideoComposition,
    validate_composition_against_scene_ids,
)


class StartCompositionRenderUseCase:
    def __init__(
        self,
        project_repo: StudioProjectRepositoryPort,
        render_job_repo: RenderJobRepositoryPort,
        composition_repo: CompositionRepositoryPort,
        execute_worker: ExecuteCompositionRenderUseCase,
    ):
        self.project_repo = project_repo
        self.render_job_repo = render_job_repo
        self.composition_repo = composition_repo
        self.execute_worker = execute_worker

    def execute(self, request: StartCompositionRenderRequestDTO) -> RenderJobDTO:
        project = self.project_repo.get_by_id(request.project_id)
        if not project:
            raise StudioProjectNotFoundException(request.project_id)
        if not project.scene_graph or not project.scene_graph.scenes:
            raise InvalidCompositionException(
                "Proje için render edilebilir bir SceneGraph bulunmuyor."
            )

        composition = self._resolve_composition(project, request.composition or {})
        validate_composition_against_scene_ids(
            composition,
            [scene.scene_id for scene in project.scene_graph.scenes],
        )
        timeline_for(composition, project.scene_graph)
        self.composition_repo.save(composition)

        existing_jobs = self.render_job_repo.list_by_project_id(request.project_id, limit=10)
        for existing in existing_jobs:
            if existing.status == RenderJobStatus.RUNNING:
                raise InvalidRenderStateException(
                    f"Bu proje için devam eden aktif bir render görevi var (ID: {existing.id}). "
                    "Lütfen tamamlanmasını bekleyin."
                )

        job_id = f"comp_{uuid.uuid4().hex[:12]}"
        job = RenderJob(
            id=job_id,
            project_id=request.project_id,
            status=RenderJobStatus.PENDING,
            progress_percent=0.0,
            current_step="Composition render queued",
        )
        saved = self.render_job_repo.save(job)

        project.transition_to(StudioProjectStatus.RENDER_QUEUED)
        self.project_repo.save(project)

        worker = threading.Thread(
            target=self.execute_worker.execute,
            args=(
                saved.id,
                request.project_id,
                composition.model_dump(mode="json"),
                request.engine_override,
                request.synthesize_voices,
            ),
            daemon=True,
            name=f"CompositionWorker-{saved.id}",
        )
        worker.start()

        return RenderJobDTO.from_entity(saved)

    def _resolve_composition(self, project, payload: Dict[str, Any]) -> VideoComposition:
        if payload:
            normalized = dict(payload)
            # A project owns exactly one composition. Deriving the ID from the
            # project keeps inline render payloads from colliding with another
            # project's saved composition.
            normalized["id"] = f"comp_{project.id}"
            normalized["project_id"] = project.id
            return VideoComposition.model_validate(normalized)

        saved = self.composition_repo.get_by_project_id(project.id)
        if saved:
            return saved

        return default_composition_for(project.id, project.scene_graph)
