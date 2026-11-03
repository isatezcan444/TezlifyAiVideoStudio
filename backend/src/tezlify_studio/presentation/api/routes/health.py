from fastapi import APIRouter, Depends
from tezlify_studio.presentation.schemas.media_schemas import SystemStatusResponse
from tezlify_studio.application.use_cases.get_system_status_use_case import GetSystemStatusUseCase
from tezlify_studio.presentation.dependencies.container import get_system_status_use_case

router = APIRouter(tags=["Health & System"])

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "Tezlify AI Video Studio",
        "version": "1.0.0"
    }

@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status(
    use_case: GetSystemStatusUseCase = Depends(get_system_status_use_case)
):
    dto = use_case.execute()
    return SystemStatusResponse(**dto.__dict__)

