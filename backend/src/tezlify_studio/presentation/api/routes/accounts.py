from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.application.use_cases.channel_selection_use_case import (
    ChannelSelectionUseCase,
)
from tezlify_studio.application.use_cases.disconnect_platform_connection_use_case import (
    DisconnectPlatformConnectionUseCase,
)
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import (
    GenerateYouTubeAuthUrlUseCase,
)
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import (
    CompleteYouTubeAuthenticationUseCase,
)
from tezlify_studio.application.use_cases.list_platform_connections_use_case import (
    ListPlatformConnectionsUseCase,
)
from tezlify_studio.domain.exceptions.creator_exceptions import ChannelNotFoundException
from tezlify_studio.infrastructure.security.oauth_desktop_listener import DesktopOAuthListener
from tezlify_studio.presentation.dependencies.container import (
    get_capability_service,
    get_channel_selection_use_case,
    get_complete_youtube_auth_use_case,
    get_disconnect_platform_connection_use_case,
    get_generate_youtube_auth_url_use_case,
    get_list_platform_connections_use_case,
    get_platform_connection_repository,
)
from tezlify_studio.presentation.schemas.account_schemas import (
    CapabilityStatusResponse,
    ConnectionListResponse,
    ConnectionResponse,
)

router = APIRouter(prefix="/social/connections", tags=["Connected Accounts"])


class GrantCapabilitiesRequest(BaseModel):
    capabilities: List[str] = Field(..., min_length=1)


@router.get("", response_model=ConnectionListResponse)
def list_connections(
    include_disconnected: bool = Query(False),
    use_case: ListPlatformConnectionsUseCase = Depends(
        get_list_platform_connections_use_case
    ),
):
    items = use_case.execute(include_disconnected=include_disconnected)
    payload = []
    for connection in items:
        data = dict(connection.__dict__)
        data["channels"] = [dict(channel.__dict__) for channel in connection.channels]
        data["capabilities"] = [
            CapabilityStatusResponse(**item.__dict__)
            for item in connection.capabilities
        ]
        data["channel_count"] = connection.channel_count
        payload.append(ConnectionResponse(**data))
    return ConnectionListResponse(items=payload, total=len(payload))


@router.delete("/{connection_id}")
def disconnect_connection(
    connection_id: str,
    use_case: DisconnectPlatformConnectionUseCase = Depends(
        get_disconnect_platform_connection_use_case
    ),
    selection_use_case: ChannelSelectionUseCase = Depends(get_channel_selection_use_case),
):
    success = use_case.execute(connection_id)
    return {
        "success": success,
        "connection_id": connection_id,
        "selection": selection_use_case.get().__dict__,
    }


@router.post("/{connection_id}/reconnect")
def reconnect_connection(
    connection_id: str,
    gen_auth_use_case: GenerateYouTubeAuthUrlUseCase = Depends(
        get_generate_youtube_auth_url_use_case
    ),
    complete_auth_use_case: CompleteYouTubeAuthenticationUseCase = Depends(
        get_complete_youtube_auth_use_case
    ),
) -> Dict[str, Any]:
    """Starts a fresh OAuth flow scoped to one existing connection."""
    listener = DesktopOAuthListener.start_new(
        oauth_handler_cb=complete_auth_use_case.execute,
        timeout_seconds=300,
    )
    try:
        dto = gen_auth_use_case.execute(
            redirect_uri=listener.redirect_uri,
            loopback_port=listener.port,
            intent="reconnect",
            connection_id=connection_id,
        )
    except Exception:
        DesktopOAuthListener.stop_current()
        raise
    return {
        "auth_url": dto.auth_url,
        "state": dto.state,
        "loopback_port": dto.loopback_port,
        "connection_id": connection_id,
    }


@router.get("/{connection_id}/capabilities", response_model=List[CapabilityStatusResponse])
def list_connection_capabilities(
    connection_id: str,
    service: YouTubeCapabilityService = Depends(get_capability_service),
    connection_repo=Depends(get_platform_connection_repository),
):
    connection = connection_repo.get_by_id(connection_id)
    if not connection:
        raise ChannelNotFoundException(connection_id)
    return [
        CapabilityStatusResponse(**status.__dict__)
        for status in service.resolve(connection)
    ]


@router.post("/{connection_id}/grant")
def grant_connection_capabilities(
    connection_id: str,
    payload: GrantCapabilitiesRequest,
    gen_auth_use_case: GenerateYouTubeAuthUrlUseCase = Depends(
        get_generate_youtube_auth_url_use_case
    ),
    complete_auth_use_case: CompleteYouTubeAuthenticationUseCase = Depends(
        get_complete_youtube_auth_use_case
    ),
) -> Dict[str, Any]:
    """Starts an incremental consent for specific capabilities.

    The OAuth request includes the connection's existing capabilities in
    addition to the new ones, so a failed or denied grant never narrows the
    working connection.
    """
    listener = DesktopOAuthListener.start_new(
        oauth_handler_cb=complete_auth_use_case.execute,
        timeout_seconds=300,
    )
    try:
        dto = gen_auth_use_case.execute(
            redirect_uri=listener.redirect_uri,
            loopback_port=listener.port,
            intent="reconnect",
            connection_id=connection_id,
            capabilities=payload.capabilities,
        )
    except Exception:
        DesktopOAuthListener.stop_current()
        raise
    return {
        "auth_url": dto.auth_url,
        "state": dto.state,
        "loopback_port": dto.loopback_port,
        "connection_id": connection_id,
        "capabilities": dto.capabilities,
        "requested_scopes": dto.requested_scopes,
    }
