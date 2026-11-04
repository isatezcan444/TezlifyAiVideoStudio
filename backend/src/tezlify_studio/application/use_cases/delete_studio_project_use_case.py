from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.domain.exceptions.studio_exceptions import StudioProjectNotFoundException
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus

class DeleteStudioProjectUseCase:
    def __init__(self, repo: StudioProjectRepositoryPort):
        self.repo = repo

    def execute(self, project_id: str, archive_only: bool = False) -> bool:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise StudioProjectNotFoundException(project_id)

        if archive_only:
            project.transition_to(StudioProjectStatus.ARCHIVED)
            self.repo.save(project)
            return True

        return self.repo.delete(project_id)
