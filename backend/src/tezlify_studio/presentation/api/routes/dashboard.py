from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from tezlify_studio.application.use_cases.get_dashboard_use_case import GetDashboardUseCase
from tezlify_studio.presentation.dependencies.container import get_dashboard_use_case

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=Dict[str, Any])
def get_dashboard(
    range_key: str = Query("28", alias="range"),
    use_case: GetDashboardUseCase = Depends(get_dashboard_use_case),
):
    """Channel status and performance snapshot built from real API + local data.

    Every block is labelled with the source that produced it. When a source is
    unavailable the response carries a warning and no fabricated values.
    """
    return use_case.execute(range_key=range_key).__dict__
