from typing import Optional, List, Tuple
from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.application.dto.studio_dto import StudioProjectDTO
from tezlify_studio.application.dto.mappers import studio_project_to_dto
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus

class ListStudioProjectsUseCase:
    def __init__(self, repo: StudioProjectRepositoryPort):
        self.repo = repo

    def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Tuple[List[StudioProjectDTO], int]:
        st = StudioProjectStatus(status) if status else None
        projects = self.repo.list_projects(limit=limit, offset=offset, status=st)
        total = self.repo.count_projects(status=st)
        return [studio_project_to_dto(p) for p in projects], total
