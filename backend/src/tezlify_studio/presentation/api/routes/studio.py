import os
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from fastapi.responses import FileResponse

from tezlify_studio.presentation.schemas.studio_schemas import (
    CreateStudioProjectRequest,
    UpdateStudioProjectRequest,
    GenerateStoryRequest,
    StudioProjectResponse,
    StudioProjectListResponse,
    GenerateStoryResponse,
)
from tezlify_studio.presentation.schemas.character_schemas import (
    CreateCharacterRequest,
    UpdateCharacterRequest,
    CharacterResponse,
    CharacterListResponse,
    StudioAssetResponse,
    StudioAssetListResponse,
)
from tezlify_studio.application.dto.studio_dto import (
    CreateStudioProjectRequestDTO,
    UpdateStudioProjectRequestDTO,
    GenerateStoryRequestDTO,
)
from tezlify_studio.application.dto.character_dto import (
    CreateCharacterRequestDTO,
    UpdateCharacterRequestDTO,
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
from tezlify_studio.application.use_cases.create_character_use_case import (
    CreateCharacterUseCase,
)
from tezlify_studio.application.use_cases.get_character_use_case import (
    GetCharacterUseCase,
)
from tezlify_studio.application.use_cases.list_characters_use_case import (
    ListCharactersUseCase,
)
from tezlify_studio.application.use_cases.update_character_use_case import (
    UpdateCharacterUseCase,
)
from tezlify_studio.application.use_cases.delete_character_use_case import (
    DeleteCharacterUseCase,
)
from tezlify_studio.application.use_cases.get_studio_asset_use_case import (
    GetStudioAssetUseCase,
)
from tezlify_studio.application.use_cases.list_studio_assets_use_case import (
    ListStudioAssetsUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_create_studio_project_use_case,
    get_generate_story_use_case,
    get_studio_project_use_case,
    get_list_studio_projects_use_case,
    get_update_studio_project_use_case,
    get_delete_studio_project_use_case,
    get_create_character_use_case,
    get_character_use_case,
    get_list_characters_use_case,
    get_update_character_use_case,
    get_delete_character_use_case,
    get_studio_asset_use_case,
    get_list_studio_assets_use_case,
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

# ==========================================
# Character Endpoints (Stage 4.2)
# ==========================================

@router.post("/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
def create_character(
    req: CreateCharacterRequest,
    use_case: CreateCharacterUseCase = Depends(get_create_character_use_case),
):
    palette_dict = req.palette.model_dump() if req.palette else None
    prop_dict = req.proportions.model_dump() if req.proportions else None
    dto = CreateCharacterRequestDTO(
        id=req.id,
        name=req.name,
        description=req.description or "",
        gender=req.gender or "neutral",
        palette=palette_dict,
        hair_style=req.hair_style or "short_parted",
        eye_style=req.eye_style or "round",
        clothing_style=req.clothing_style or "casual",
        voice_id=req.voice_id or "",
        default_expression=req.default_expression or "neutral",
        default_pose=req.default_pose or "standing",
        proportions=prop_dict,
    )
    res = use_case.execute(dto)
    return res.__dict__

@router.get("/characters", response_model=CharacterListResponse)
def list_characters(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    gender: Optional[str] = Query(None),
    is_builtin: Optional[bool] = Query(None),
    use_case: ListCharactersUseCase = Depends(get_list_characters_use_case),
):
    items, total = use_case.execute(limit=limit, offset=offset, gender=gender, is_builtin=is_builtin)
    return {
        "items": [item.__dict__ for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.get("/characters/{character_id}", response_model=CharacterResponse)
def get_character(
    character_id: str = Path(..., min_length=1),
    use_case: GetCharacterUseCase = Depends(get_character_use_case),
):
    res = use_case.execute(character_id)
    return res.__dict__

@router.put("/characters/{character_id}", response_model=CharacterResponse)
def update_character(
    character_id: str = Path(..., min_length=1),
    req: UpdateCharacterRequest = ...,
    use_case: UpdateCharacterUseCase = Depends(get_update_character_use_case),
):
    palette_dict = req.palette.model_dump() if req.palette is not None else None
    prop_dict = req.proportions.model_dump() if req.proportions is not None else None
    dto = UpdateCharacterRequestDTO(
        name=req.name,
        description=req.description,
        gender=req.gender,
        palette=palette_dict,
        hair_style=req.hair_style,
        eye_style=req.eye_style,
        clothing_style=req.clothing_style,
        voice_id=req.voice_id,
        default_expression=req.default_expression,
        default_pose=req.default_pose,
        proportions=prop_dict,
    )
    res = use_case.execute(character_id, dto)
    return res.__dict__

@router.delete("/characters/{character_id}", status_code=status.HTTP_200_OK)
def delete_character(
    character_id: str = Path(..., min_length=1),
    use_case: DeleteCharacterUseCase = Depends(get_delete_character_use_case),
):
    deleted = use_case.execute(character_id)
    return {"id": character_id, "deleted": deleted}

@router.get("/characters/{character_id}/thumbnail")
def get_character_thumbnail(
    character_id: str = Path(..., min_length=1),
    use_case: GetCharacterUseCase = Depends(get_character_use_case),
):
    char = use_case.execute(character_id)
    if char.thumbnail_path and os.path.isfile(char.thumbnail_path):
        return FileResponse(char.thumbnail_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Karakter önizleme görseli bulunamadı.")

# ==========================================
# Asset Endpoints (Stage 4.2)
# ==========================================

@router.get("/assets", response_model=StudioAssetListResponse)
def list_assets(
    category: Optional[str] = Query(None, pattern="^(background|prop|lighting)$"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    use_case: ListStudioAssetsUseCase = Depends(get_list_studio_assets_use_case),
):
    items, total = use_case.execute(category=category, limit=limit, offset=offset)
    return {
        "items": [item.__dict__ for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.get("/assets/{asset_id}", response_model=StudioAssetResponse)
def get_asset(
    asset_id: str = Path(..., min_length=1),
    use_case: GetStudioAssetUseCase = Depends(get_studio_asset_use_case),
):
    res = use_case.execute(asset_id)
    return res.__dict__

@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(
    asset_id: str = Path(..., min_length=1),
    use_case: GetStudioAssetUseCase = Depends(get_studio_asset_use_case),
):
    asset = use_case.execute(asset_id)
    if asset.thumbnail_path and os.path.isfile(asset.thumbnail_path):
        return FileResponse(asset.thumbnail_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Varlık önizleme görseli bulunamadı.")

