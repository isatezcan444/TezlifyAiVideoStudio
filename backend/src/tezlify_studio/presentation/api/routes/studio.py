from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status

from tezlify_studio.presentation.schemas.studio_schemas import (
    CreateStudioProjectRequest,
    UpdateStudioProjectRequest,
    GenerateStoryRequest,
    StudioProjectResponse,
    StudioProjectListResponse,
    GenerateStoryResponse,
)
from tezlify_studio.application.dto.studio_dto import (
    CreateStudioProjectRequestDTO,
    UpdateStudioProjectRequestDTO,
    GenerateStoryRequestDTO,
)
from tezlify_studio.application.use_cases.create_studio_project_use_case import (
    CreateStudioProjectUseCase,
)
from tezlify_studio.application.use_cases.generate_story_scene_graph_use_case import (
    GenerateStorySceneGraphUseCase,
)
from tezlify_studio.application.use_cases.get_studio_project_use_case import (
    GetStudioProjectUseCase,
)
from tezlify_studio.application.use_cases.list_studio_projects_use_case import (
    ListStudioProjectsUseCase,
)
from tezlify_studio.application.use_cases.update_studio_project_use_case import (
    UpdateStudioProjectUseCase,
)
from tezlify_studio.application.use_cases.delete_studio_project_use_case import (
    DeleteStudioProjectUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_create_studio_project_use_case,
    get_generate_story_use_case,
    get_studio_project_use_case,
    get_list_studio_projects_use_case,
    get_update_studio_project_use_case,
    get_delete_studio_project_use_case,
)

router = APIRouter(prefix="/studio", tags=["AI Studio"])

@router.post("/projects", response_model=StudioProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    req: CreateStudioProjectRequest,
    use_case: CreateStudioProjectUseCase = Depends(get_create_studio_project_use_case),
):
    dto = CreateStudioProjectRequestDTO(
        title=req.title,
        description=req.description or "",
        scene_graph=req.scene_graph,
    )
    result = use_case.execute(dto)
    return result.__dict__

@router.get("/projects", response_model=StudioProjectListResponse)
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    use_case: ListStudioProjectsUseCase = Depends(get_list_studio_projects_use_case),
):
    items, total = use_case.execute(limit=limit, offset=offset, status=status)
    return {
        "items": [item.__dict__ for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.get("/projects/{project_id}", response_model=StudioProjectResponse)
def get_project(
    project_id: str = Path(..., min_length=1),
    use_case: GetStudioProjectUseCase = Depends(get_studio_project_use_case),
):
    result = use_case.execute(project_id)
    return result.__dict__

@router.put("/projects/{project_id}", response_model=StudioProjectResponse)
def update_project(
    project_id: str = Path(..., min_length=1),
    req: UpdateStudioProjectRequest = ...,
    use_case: UpdateStudioProjectUseCase = Depends(get_update_studio_project_use_case),
):
    dto = UpdateStudioProjectRequestDTO(
        title=req.title,
        description=req.description,
        status=req.status,
        scene_graph=req.scene_graph,
    )
    result = use_case.execute(project_id, dto)
    return result.__dict__

@router.delete("/projects/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(
    project_id: str = Path(..., min_length=1),
    archive: bool = Query(False, description="Archive project instead of hard deleting"),
    use_case: DeleteStudioProjectUseCase = Depends(get_delete_studio_project_use_case),
):
    deleted = use_case.execute(project_id, archive_only=archive)
    return {"id": project_id, "deleted": deleted, "archived": archive}

@router.post("/generate-story", response_model=GenerateStoryResponse)
def generate_story(
    req: GenerateStoryRequest,
    use_case: GenerateStorySceneGraphUseCase = Depends(get_generate_story_use_case),
):
    dto = GenerateStoryRequestDTO(
        prompt=req.prompt,
        target_duration_seconds=req.target_duration_seconds,
        aspect_ratio=req.aspect_ratio or "16:9",
        genre=req.genre,
        provider=req.provider,
    )
    scene_graph = use_case.execute(dto)
    sg_dict = scene_graph.model_dump()
    return {
        "scene_graph": sg_dict,
        "total_duration_seconds": scene_graph.total_duration_seconds,
        "scene_count": len(scene_graph.scenes),
        "character_count": len(scene_graph.characters),
    }
