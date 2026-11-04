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
from tezlify_studio.presentation.schemas.render_schemas import (
    StartRenderRequest,
    RenderJobResponse,
    RenderJobListResponse,
)
from tezlify_studio.presentation.schemas.voice_schemas import (
    VoiceResponse,
    VoiceListResponse,
    VoiceStatusResponse,
    VoicePreviewRequest,
)
from tezlify_studio.presentation.schemas.composition_schemas import (
    SaveCompositionRequest,
    StartCompositionRenderRequest,
    CompositionSummaryResponse,
)
from tezlify_studio.application.dto.render_dto import (
    StartRenderRequestDTO,
)
from tezlify_studio.application.use_cases.start_project_render_use_case import (
    StartProjectRenderUseCase,
)
from tezlify_studio.application.use_cases.get_render_job_use_case import (
    GetRenderJobUseCase,
)
from tezlify_studio.application.use_cases.list_project_renders_use_case import (
    ListProjectRendersUseCase,
)
from tezlify_studio.application.use_cases.list_render_jobs_use_case import (
    ListRenderJobsUseCase,
)
from tezlify_studio.application.use_cases.cancel_render_job_use_case import (
    CancelRenderJobUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_cancel_render_job_use_case,
)
from tezlify_studio.domain.enums.studio_status import RenderJobStatus
from tezlify_studio.application.use_cases.list_voices_use_case import (
    ListVoicesUseCase,
)
from tezlify_studio.application.use_cases.synthesize_dialogue_audio_use_case import (
    SynthesizeDialogueAudioUseCase,
)
from tezlify_studio.application.dto.studio_dto import (
    CreateStudioProjectRequestDTO,
    UpdateStudioProjectRequestDTO,
    GenerateStoryRequestDTO,
)
from tezlify_studio.application.dto.composition_dto import (
    StartCompositionRenderRequestDTO,
)
from tezlify_studio.application.use_cases.get_project_composition_use_case import (
    GetProjectCompositionUseCase,
)
from tezlify_studio.application.use_cases.save_project_composition_use_case import (
    SaveProjectCompositionUseCase,
)
from tezlify_studio.application.use_cases.start_composition_render_use_case import (
    StartCompositionRenderUseCase,
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
    get_start_project_render_use_case,
    get_render_job_use_case,
    get_list_project_renders_use_case,
    get_list_render_jobs_use_case,
    get_list_voices_use_case,
    get_synthesize_dialogue_audio_use_case,
    get_project_composition_use_case,
    get_save_project_composition_use_case,
    get_start_composition_render_use_case,
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

# ==========================================
# Render Engine Endpoints (Stage 4.3)
# ==========================================

@router.post(
    "/projects/{project_id}/render",
    response_model=RenderJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_render(
    project_id: str = Path(..., min_length=1),
    req: Optional[StartRenderRequest] = None,
    use_case: StartProjectRenderUseCase = Depends(get_start_project_render_use_case),
):
    dto = StartRenderRequestDTO(
        project_id=project_id,
        engine_override=req.engine_override if req else None,
        synthesize_voices=req.synthesize_voices if (req and req.synthesize_voices is not None) else True,
    )
    res = use_case.execute(dto)
    return res.__dict__

@router.get(
    "/projects/{project_id}/renders",
    response_model=RenderJobListResponse,
    status_code=status.HTTP_200_OK,
)
def list_project_renders(
    project_id: str = Path(..., min_length=1),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    use_case: ListProjectRendersUseCase = Depends(get_list_project_renders_use_case),
):
    jobs = use_case.execute(project_id, limit=limit, offset=offset)
    items = []
    for j in jobs:
        item = j.__dict__
        item.pop("output_video_path", None)
        items.append(item)
    return {
        "items": items,
        "total": len(jobs),
    }

@router.get(
    "/renders",
    response_model=RenderJobListResponse,
    status_code=status.HTTP_200_OK,
)
def list_render_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    job_status: Optional[str] = Query(
        None,
        alias="status",
        pattern="^(pending|running|completed|failed|cancelled)$",
    ),
    use_case: ListRenderJobsUseCase = Depends(get_list_render_jobs_use_case),
):
    status_filter = RenderJobStatus(job_status) if job_status else None
    jobs, total = use_case.execute(limit=limit, offset=offset, status=status_filter)
    items = []
    for job in jobs:
        item = job.__dict__
        item.pop("output_video_path", None)
        items.append(item)
    return {
        "items": items,
        "total": total,
    }


def _iso(value) -> Optional[str]:
    """Convert a datetime or date-like value to an ISO string, pass-through strings."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _render_job_to_dict(job) -> dict:
    """Serialize a RenderJob domain entity to a JSON-safe dict.

    Datetime fields are converted to ISO strings and the absolute server file
    path is omitted so it is not leaked to API consumers.
    """
    output_metadata = None
    if job.output_metadata is not None:
        try:
            output_metadata = job.output_metadata.model_dump()
        except Exception:
            output_metadata = str(job.output_metadata)

    return {
        "id": job.id,
        "project_id": job.project_id,
        "status": job.status.value if hasattr(job.status, "value") else job.status,
        "progress_percent": job.progress_percent,
        "current_step": job.current_step,
        # output_video_path intentionally omitted (internal server path)
        "output_metadata": output_metadata,
        "error_message": job.error_message,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "completed_at": _iso(job.completed_at),
    }


@router.get(
    "/renders/{job_id}",
    response_model=RenderJobResponse,
    status_code=status.HTTP_200_OK,
)
def get_render_job(
    job_id: str = Path(..., min_length=1),
    use_case: GetRenderJobUseCase = Depends(get_render_job_use_case),
):
    res = use_case.execute(job_id)
    return _render_job_to_dict(res)


@router.post(
    "/renders/{job_id}/cancel",
    response_model=RenderJobResponse,
    status_code=status.HTTP_200_OK,
)
def cancel_render_job(
    job_id: str = Path(..., min_length=1),
    use_case: CancelRenderJobUseCase = Depends(get_cancel_render_job_use_case),
):
    job = use_case.execute(job_id)
    return _render_job_to_dict(job)

@router.get("/renders/{job_id}/video")
def stream_render_video(
    job_id: str = Path(..., min_length=1),
    use_case: GetRenderJobUseCase = Depends(get_render_job_use_case),
):
    job = use_case.execute(job_id)
    if not job.output_video_path or not os.path.isfile(job.output_video_path):
        raise HTTPException(
            status_code=404,
            detail=f"Render videosu henüz mevcut değil veya işleniyor (Durum: {job.status}).",
        )
    return FileResponse(
        job.output_video_path,
        media_type="video/mp4",
        filename=f"render_{job_id}.mp4",
    )

# ==========================================
# ElevenLabs AI Voice Endpoints (Stage 4.4)
# ==========================================

@router.get(
    "/voices",
    response_model=VoiceListResponse,
    status_code=status.HTTP_200_OK,
)
def list_voices(
    use_case: ListVoicesUseCase = Depends(get_list_voices_use_case),
):
    res = use_case.execute()
    return res.model_dump()

@router.get(
    "/voices/status",
    response_model=VoiceStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_voice_status(
    use_case: ListVoicesUseCase = Depends(get_list_voices_use_case),
):
    from tezlify_studio.infrastructure.configuration.settings import settings
    return {
        "is_configured": use_case.voice_synthesizer.is_configured(),
        "default_model": settings.elevenlabs_default_model,
        "provider": "ElevenLabs",
    }

# ==========================================
# Video Composition Studio (Stage 4.5)
# ==========================================

@router.get(
    "/projects/{project_id}/composition",
    response_model=CompositionSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_composition(
    project_id: str = Path(..., min_length=1),
    use_case: GetProjectCompositionUseCase = Depends(get_project_composition_use_case),
):
    return use_case.execute(project_id).model_dump()


@router.put(
    "/projects/{project_id}/composition",
    response_model=CompositionSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def save_project_composition(
    project_id: str = Path(..., min_length=1),
    req: SaveCompositionRequest = ...,
    use_case: SaveProjectCompositionUseCase = Depends(get_save_project_composition_use_case),
):
    return use_case.execute(project_id, req.composition).model_dump()


@router.post(
    "/projects/{project_id}/composition/render",
    response_model=RenderJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_composition_render(
    project_id: str = Path(..., min_length=1),
    req: Optional[StartCompositionRenderRequest] = None,
    use_case: StartCompositionRenderUseCase = Depends(get_start_composition_render_use_case),
):
    dto = StartCompositionRenderRequestDTO(
        project_id=project_id,
        composition=req.composition if req else None,
        engine_override=req.engine_override if req else None,
        synthesize_voices=req.synthesize_voices if (req and req.synthesize_voices is not None) else True,
    )
    return use_case.execute(dto).__dict__


@router.get("/renders/{job_id}/subtitles")
def download_render_subtitles(
    job_id: str = Path(..., min_length=1),
    use_case: GetRenderJobUseCase = Depends(get_render_job_use_case),
):
    job = use_case.execute(job_id)
    subtitle_path = None
    if job.output_metadata:
        # RenderJobDTO serialises metadata as a plain dict.
        subtitle_path = job.output_metadata.get("subtitle_file_path")
    if not subtitle_path or not os.path.isfile(subtitle_path):
        raise HTTPException(status_code=404, detail="Bu render için SRT altyazı dosyası bulunamadı.")
    return FileResponse(
        subtitle_path,
        media_type="application/x-subrip",
        filename=f"{job_id}.srt",
    )



