import uuid
import threading
from typing import Optional
from tezlify_studio.application.ports.render_job_repository_port import RenderJobRepositoryPort
from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.application.dto.render_dto import RenderJobDTO, StartRenderRequestDTO
from tezlify_studio.application.use_cases.execute_render_job_use_case import ExecuteRenderJobUseCase
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus, StudioProjectStatus
from tezlify_studio.domain.exceptions.studio_exceptions import (
    StudioProjectNotFoundException,
    InvalidSceneGraphException,
    InvalidRenderStateException,
)

class StartProjectRenderUseCase:
    def __init__(
        self,
        project_repo: StudioProjectRepositoryPort,
        render_job_repo: RenderJobRepositoryPort,
        execute_worker: ExecuteRenderJobUseCase,
    ):
        self.project_repo = project_repo
        self.render_job_repo = render_job_repo
        self.execute_worker = execute_worker

    def execute(self, request: StartRenderRequestDTO) -> RenderJobDTO:
        project = self.project_repo.get_by_id(request.project_id)
        if not project:
            raise StudioProjectNotFoundException(request.project_id)

        if not project.scene_graph:
            raise InvalidSceneGraphException("Proje için henüz bir SceneGraph oluşturulmamış.")

        if not project.scene_graph.scenes:
            raise InvalidSceneGraphException("SceneGraph içinde en az 1 sahne bulunmalıdır.")

        # Check existing running jobs for this project
        existing_jobs = self.render_job_repo.list_by_project_id(request.project_id, limit=5)
        for ej in existing_jobs:
            if ej.status == RenderJobStatus.RUNNING:
                raise InvalidRenderStateException(
                    f"Bu proje için devam eden aktif bir render görevi var (ID: {ej.id}). Lütfen tamamlanmasını bekleyin."
                )

        job_id = f"render_{uuid.uuid4().hex[:12]}"
        job = RenderJob(
            id=job_id,
            project_id=request.project_id,
            status=RenderJobStatus.PENDING,
            progress_percent=0.0,
            current_step="Pending render dispatch",
        )
        saved_job = self.render_job_repo.save(job)

        project.transition_to(StudioProjectStatus.RENDER_QUEUED)
        self.project_repo.save(project)

        # Launch background render worker thread
        worker_thread = threading.Thread(
            target=self.execute_worker.execute,
            args=(saved_job.id, request.project_id, request.engine_override, request.synthesize_voices),
            daemon=True,
            name=f"RenderWorker-{saved_job.id}",
        )
        worker_thread.start()

        return RenderJobDTO.from_entity(saved_job)
