from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from tezlify_studio.application.use_cases.get_dashboard_use_case import GetDashboardUseCase
from tezlify_studio.application.use_cases.get_global_dashboard_use_case import (
    GetGlobalDashboardUseCase,
)
from tezlify_studio.presentation.dependencies.container import (
    get_dashboard_use_case,
    get_global_dashboard_use_case,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=Dict[str, Any])
def get_dashboard(
    range_key: str = Query("28", alias="range"),
    channel_id: Optional[str] = Query(
        None,
        description="Target channel id. Omit to use the globally selected channel.",
    ),
    use_case: GetDashboardUseCase = Depends(get_dashboard_use_case),
):
    """Channel status and performance snapshot built from real API + local data.

    Every block is labelled with the source that produced it. When a source is
    unavailable the response carries a warning and no fabricated values.
    """
    return use_case.execute(range_key=range_key, channel_id=channel_id).__dict__


@router.get("/global", response_model=Dict[str, Any])
def get_global_dashboard(
    use_case: GetGlobalDashboardUseCase = Depends(get_global_dashboard_use_case),
):
    """Workspace-wide overview of accounts, channels and local publish records.

    YouTube metrics are intentionally not summed across channels here.
    """
    return use_case.execute()
