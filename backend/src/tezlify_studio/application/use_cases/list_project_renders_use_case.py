from typing import List
from tezlify_studio.application.ports.render_job_repository_port import RenderJobRepositoryPort
from tezlify_studio.application.dto.render_dto import RenderJobDTO

class ListProjectRendersUseCase:
    def __init__(self, render_job_repo: RenderJobRepositoryPort):
        self.render_job_repo = render_job_repo

    def execute(self, project_id: str, limit: int = 50, offset: int = 0) -> List[RenderJobDTO]:
        jobs = self.render_job_repo.list_by_project_id(project_id, limit=limit, offset=offset)
        return [RenderJobDTO.from_entity(j) for j in jobs]
