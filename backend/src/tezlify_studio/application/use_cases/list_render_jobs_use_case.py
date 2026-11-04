from typing import List, Optional, Tuple

from tezlify_studio.application.dto.render_dto import RenderJobDTO
from tezlify_studio.application.ports.render_job_repository_port import RenderJobRepositoryPort
from tezlify_studio.domain.enums.studio_status import RenderJobStatus


class ListRenderJobsUseCase:
    """Read-only global render history used by the unified Studio workspace."""

    def __init__(self, render_job_repo: RenderJobRepositoryPort):
        self.render_job_repo = render_job_repo

    def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[RenderJobStatus] = None,
    ) -> Tuple[List[RenderJobDTO], int]:
        jobs = self.render_job_repo.list_jobs(limit=limit, offset=offset, status=status)
        total = self.render_job_repo.count_jobs(status=status)
        return [RenderJobDTO.from_entity(job) for job in jobs], total
