"""Central resolver for per-connection YouTube capabilities.

Every permission decision in the application goes through this service. It
looks only at the connection's own grant, so capabilities never leak between
accounts. It also keeps "API not enabled in Google Cloud" separate from
"scope was not granted", because the two need different user actions.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.connection_status import ConnectionStatus
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ConnectionInactiveException,
    InsufficientScopeException,
)
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    CAPABILITY_ANALYTICS,
    CAPABILITY_CHANNEL_READ,
    CAPABILITY_COMMENTS,
    CAPABILITY_IDENTITY,
    CAPABILITY_REVENUE,
    CAPABILITY_SCOPE_MAP,
    CAPABILITY_STATUS_ACTIVE,
    CAPABILITY_STATUS_API_NOT_ENABLED,
    CAPABILITY_STATUS_REAUTH_REQUIRED,
    CAPABILITY_STATUS_SCOPE_REQUIRED,
    CAPABILITY_STATUS_UNAVAILABLE,
    CAPABILITY_UPLOAD,
    KNOWN_CAPABILITIES,
    OPTIONAL_CAPABILITIES,
    has_capability,
)

ApiStateProvider = Callable[[str, str], Optional[str]]

_ACTION_TEXT = {
    CAPABILITY_IDENTITY: "Google hesap kimliğini okuma",
    CAPABILITY_CHANNEL_READ: "YouTube kanal verilerini okuma",
    CAPABILITY_ANALYTICS: "YouTube Analytics verilerini okuma",
    CAPABILITY_UPLOAD: "YouTube'a video yükleme",
    CAPABILITY_COMMENTS: "YouTube yorumlarını yanıtlama ve yönetme",
    CAPABILITY_REVENUE: "YouTube gelir verilerini okuma",
}


@dataclass(frozen=True)
class CapabilityStatus:
    capability: str
    status: str
    granted: bool
    optional: bool
    required_scopes: List[str]


class YouTubeCapabilityService:
    def __init__(self, api_state_provider: Optional[ApiStateProvider] = None):
        self.api_state_provider = api_state_provider

    def resolve(self, connection: PlatformConnection) -> List[CapabilityStatus]:
        statuses: List[CapabilityStatus] = []
        for capability in KNOWN_CAPABILITIES:
            granted = has_capability(connection.granted_scopes, capability)
            if connection.connection_status == ConnectionStatus.REAUTH_REQUIRED:
                status = CAPABILITY_STATUS_REAUTH_REQUIRED
            elif not connection.is_active:
                status = CAPABILITY_STATUS_UNAVAILABLE
            elif not granted:
                status = CAPABILITY_STATUS_SCOPE_REQUIRED
            elif (
                capability == CAPABILITY_ANALYTICS
                and self.api_state_provider
                and self.api_state_provider(connection.id, capability)
                == CAPABILITY_STATUS_API_NOT_ENABLED
            ):
                status = CAPABILITY_STATUS_API_NOT_ENABLED
            else:
                status = CAPABILITY_STATUS_ACTIVE
            statuses.append(
                CapabilityStatus(
                    capability=capability,
                    status=status,
                    granted=granted,
                    optional=capability in OPTIONAL_CAPABILITIES,
                    required_scopes=list(CAPABILITY_SCOPE_MAP[capability]),
                )
            )
        return statuses

    def status_map(self, connection: PlatformConnection) -> Dict[str, CapabilityStatus]:
        return {item.capability: item for item in self.resolve(connection)}

    def can(self, connection: PlatformConnection, capability: str) -> bool:
        if not connection.is_active:
            return False
        if capability == CAPABILITY_ANALYTICS and self.api_state_provider:
            if (
                self.api_state_provider(connection.id, capability)
                == CAPABILITY_STATUS_API_NOT_ENABLED
            ):
                return False
        return has_capability(connection.granted_scopes, capability)

    def require(self, connection: PlatformConnection, capability: str) -> None:
        if not connection.is_active:
            raise ConnectionInactiveException(
                connection.id, connection.connection_status.value
            )
        if has_capability(connection.granted_scopes, capability):
            return
        required = CAPABILITY_SCOPE_MAP.get(capability)
        if not required:
            raise ValueError(f"Bilinmeyen yetenek: {capability}")
        raise InsufficientScopeException(
            required_scope=required[0],
            action=_ACTION_TEXT.get(capability, capability),
            capability=capability,
        )

    @staticmethod
    def granted_capabilities(scopes: Iterable[str]) -> List[str]:
        scope_set = set(scopes or ())
        return [
            capability
            for capability, required in CAPABILITY_SCOPE_MAP.items()
            if required and all(scope in scope_set for scope in required)
        ]
