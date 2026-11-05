from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from tezlify_studio.application.use_cases.list_platforms_use_case import ListPlatformsUseCase
from tezlify_studio.presentation.dependencies.container import get_list_platforms_use_case

router = APIRouter(prefix="/platforms", tags=["Platforms"])


@router.get("", response_model=List[Dict[str, Any]])
def list_platforms(
    use_case: ListPlatformsUseCase = Depends(get_list_platforms_use_case),
):
    """List known publishing platforms and their real capabilities.

    Only YouTube is implemented; no placeholder platforms are advertised.
    """
    return [descriptor.__dict__ for descriptor in use_case.execute()]
