from typing import Any, Dict

from tezlify_studio.application.dto.composition_dto import CompositionSummaryDTO
from tezlify_studio.application.ports.composition_repository_port import (
    CompositionRepositoryPort,
)
from tezlify_studio.application.ports.studio_project_repository_port import (
    StudioProjectRepositoryPort,
)
from tezlify_studio.application.services.composition_factory import (
    default_composition_for,
    timeline_for,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidSceneGraphException,
    StudioProjectNotFoundException,
)
from tezlify_studio.domain.value_objects.video_composition import (
    CompositionTransition,
    VideoComposition,
)


def build_composition_summary(
    composition: VideoComposition,
    scene_graph,
    is_saved: bool,
) -> CompositionSummaryDTO:
    timeline = timeline_for(composition, scene_graph)
    return CompositionSummaryDTO(
        composition=composition.model_dump(mode="json"),
        timeline=[
            {
                "scene_id": entry.scene_id,
                "order": entry.order,
                "duration_seconds": entry.duration_seconds,
                "start_time": entry.start_time,
                "end_time": entry.end_time,
                "transition": entry.transition.value,
                "transition_duration_seconds": entry.transition_duration_seconds,
            }
            for entry in timeline.entries
        ],
        total_duration_seconds=timeline.total_duration_seconds,
        scene_count=len(composition.scenes),
        text_layer_count=len(composition.text_layers),
        transition_count=sum(
            1 for entry in timeline.entries if entry.transition != CompositionTransition.CUT
        ),
        is_saved=is_saved,
    )


class GetProjectCompositionUseCase:
    def __init__(
        self,
        project_repo: StudioProjectRepositoryPort,
        composition_repo: CompositionRepositoryPort,
    ):
        self.project_repo = project_repo
        self.composition_repo = composition_repo

    def execute(self, project_id: str) -> CompositionSummaryDTO:
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise StudioProjectNotFoundException(project_id)
        if not project.scene_graph or not project.scene_graph.scenes:
            raise InvalidSceneGraphException("Proje için henüz bir SceneGraph oluşturulmamış.")

        saved = self.composition_repo.get_by_project_id(project_id)
        if saved:
            return build_composition_summary(saved, project.scene_graph, is_saved=True)

        default = default_composition_for(project_id, project.scene_graph)
        return build_composition_summary(default, project.scene_graph, is_saved=False)
