from typing import Any, Dict

from tezlify_studio.application.dto.composition_dto import CompositionSummaryDTO
from tezlify_studio.application.ports.composition_repository_port import (
    CompositionRepositoryPort,
)
from tezlify_studio.application.ports.studio_project_repository_port import (
    StudioProjectRepositoryPort,
)
from tezlify_studio.application.use_cases.get_project_composition_use_case import (
    build_composition_summary,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidSceneGraphException,
    StudioProjectNotFoundException,
)
from tezlify_studio.domain.value_objects.video_composition import (
    VideoComposition,
    validate_composition_against_scene_ids,
)


class SaveProjectCompositionUseCase:
    def __init__(
        self,
        project_repo: StudioProjectRepositoryPort,
        composition_repo: CompositionRepositoryPort,
    ):
        self.project_repo = project_repo
        self.composition_repo = composition_repo

    def execute(self, project_id: str, payload: Dict[str, Any]) -> CompositionSummaryDTO:
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise StudioProjectNotFoundException(project_id)
        if not project.scene_graph or not project.scene_graph.scenes:
            raise InvalidSceneGraphException("Proje için henüz bir SceneGraph oluşturulmamış.")

        normalized = dict(payload or {})
        # One composition per project; the project-derived ID is the stable
        # identity used by the API and the composition repository.
        normalized["id"] = f"comp_{project_id}"
        normalized["project_id"] = project_id

        composition = VideoComposition.model_validate(normalized)
        validate_composition_against_scene_ids(
            composition,
            [scene.scene_id for scene in project.scene_graph.scenes],
        )
        # Building the timeline here validates crossfade durations before saving.
        build_composition_summary(composition, project.scene_graph, is_saved=True)

        saved = self.composition_repo.save(composition)
        return build_composition_summary(saved, project.scene_graph, is_saved=True)
