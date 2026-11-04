from typing import Optional
from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.application.dto.studio_dto import UpdateStudioProjectRequestDTO, StudioProjectDTO
from tezlify_studio.application.dto.mappers import studio_project_to_dto
from tezlify_studio.domain.exceptions.studio_exceptions import StudioProjectNotFoundException
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph

class UpdateStudioProjectUseCase:
    def __init__(self, repo: StudioProjectRepositoryPort):
        self.repo = repo

    def execute(self, project_id: str, req: UpdateStudioProjectRequestDTO) -> StudioProjectDTO:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise StudioProjectNotFoundException(project_id)

        if req.scene_graph is not None:
            # Ensure project_id matches
            sg_data = dict(req.scene_graph)
            sg_data["project_id"] = project_id
            validated_sg = SceneGraph.model_validate(sg_data)
            project.update_scene_graph(validated_sg)

        if req.title is not None or req.description is not None:
            project.update_metadata(title=req.title, description=req.description)

        if req.status is not None:
            project.transition_to(StudioProjectStatus(req.status))

        saved = self.repo.save(project)
        return studio_project_to_dto(saved)
