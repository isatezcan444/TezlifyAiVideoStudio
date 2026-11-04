import uuid
from typing import Optional
from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.application.dto.studio_dto import CreateStudioProjectRequestDTO, StudioProjectDTO
from tezlify_studio.application.dto.mappers import studio_project_to_dto
from tezlify_studio.domain.entities.studio_project import StudioProject
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    SceneResolution,
    SceneCharacter,
    CharacterStyle,
    StudioScene,
    SceneBackground,
    SceneCamera,
    CharacterPlacement,
    SceneDialogue,
)

class CreateStudioProjectUseCase:
    def __init__(self, repo: StudioProjectRepositoryPort):
        self.repo = repo

    def execute(self, req: CreateStudioProjectRequestDTO) -> StudioProjectDTO:
        project_id = f"proj_{uuid.uuid4().hex[:10]}"
        clean_title = req.title.strip()
        if not clean_title:
            raise ValueError("Proje başlığı boş olamaz.")

        if req.scene_graph:
            # Ensure project_id matches if missing
            sg_data = dict(req.scene_graph)
            if not sg_data.get("project_id"):
                sg_data["project_id"] = project_id
            if not sg_data.get("title"):
                sg_data["title"] = clean_title
            scene_graph = SceneGraph.model_validate(sg_data)
            status = StudioProjectStatus.SCENARIO_READY
        else:
            # Default minimal valid draft SceneGraph
            char = SceneCharacter(
                id="char_01",
                name="Karakter 1",
                voice_id="tr_yelda",
                style=CharacterStyle(),
            )
            scene = StudioScene(
                scene_id="scene_01",
                sequence_order=1,
                duration_seconds=15.0,
                background=SceneBackground(),
                camera=SceneCamera(),
                character_placements=[
                    CharacterPlacement(character_id="char_01", position=[0.0, 0.0, 0.0])
                ],
                dialogues=[
                    SceneDialogue(
                        character_id="char_01",
                        start_time=1.0,
                        end_time=5.0,
                        text="Tezlify AI Studio'ya hoş geldiniz!",
                    )
                ],
            )
            scene_graph = SceneGraph(
                schema_version="1.0",
                project_id=project_id,
                title=clean_title,
                description=req.description or "",
                resolution=SceneResolution(),
                characters=[char],
                scenes=[scene],
            )
            status = StudioProjectStatus.DRAFT

        project = StudioProject(
            id=project_id,
            title=clean_title,
            description=req.description or "",
            status=status,
            scene_graph=scene_graph,
        )

        saved = self.repo.save(project)
        return studio_project_to_dto(saved)
