from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.application.dto.studio_dto import StudioProjectDTO
from tezlify_studio.application.dto.mappers import studio_project_to_dto
from tezlify_studio.domain.exceptions.studio_exceptions import StudioProjectNotFoundException

class GetStudioProjectUseCase:
    def __init__(self, repo: StudioProjectRepositoryPort):
        self.repo = repo

    def execute(self, project_id: str) -> StudioProjectDTO:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise StudioProjectNotFoundException(project_id)
        return studio_project_to_dto(project)
