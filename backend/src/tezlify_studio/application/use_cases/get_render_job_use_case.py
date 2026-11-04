from tezlify_studio.application.ports.render_job_repository_port import RenderJobRepositoryPort
from tezlify_studio.application.dto.render_dto import RenderJobDTO
from tezlify_studio.domain.exceptions.studio_exceptions import RenderJobNotFoundException

class GetRenderJobUseCase:
    def __init__(self, render_job_repo: RenderJobRepositoryPort):
        self.render_job_repo = render_job_repo

    def execute(self, job_id: str) -> RenderJobDTO:
        job = self.render_job_repo.get_by_id(job_id)
        if not job:
            raise RenderJobNotFoundException(job_id)
        return RenderJobDTO.from_entity(job)
