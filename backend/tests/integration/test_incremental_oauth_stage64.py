"""Stage 6.4 contracts: incremental OAuth capabilities per connection.

Everything here runs against in-memory ports and a fake publisher. No request
reaches Google, so a green run proves the local contracts only; it is not live
Google OAuth acceptance.
"""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.services.analytics_availability_registry import (
    AnalyticsAvailabilityRegistry,
)
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import (
    CompleteYouTubeAuthenticationUseCase,
)
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import (
    GenerateYouTubeAuthUrlUseCase,
)
from tezlify_studio.application.use_cases.get_channel_analytics_use_case import (
    GetChannelAnalyticsUseCase,
)
from tezlify_studio.domain.entities.channel_selection import ChannelSelection
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.connection_status import ConnectionStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelNotFoundException,
    ConnectionInactiveException,
    DuplicateOAuthCallbackException,
    InsufficientScopeException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
)
from tezlify_studio.domain.value_objects.creator_models import AnalyticsResult
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    BASE_CAPABILITIES,
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
    OPTIONAL_CAPABILITIES,
    SCOPE_ANALYTICS,
    SCOPE_CHANNEL_READ,
    SCOPE_COMMENTS,
    SCOPE_EMAIL,
    SCOPE_OPENID,
    SCOPE_PROFILE,
    SCOPE_REVENUE,
    SCOPE_UPLOAD,
    capabilities_for_scopes,
    has_capability,
    merge_capability_scopes,
    normalize_capabilities,
    scopes_for_capabilities,
)

BASE_SCOPES = [SCOPE_OPENID, SCOPE_EMAIL, SCOPE_PROFILE, SCOPE_CHANNEL_READ]


# ---------------------------------------------------------------------------
# In-memory ports
# ---------------------------------------------------------------------------
class FakeConnectionRepo(PlatformConnectionRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, PlatformConnection] = {}

    def save(self, connection: PlatformConnection) -> PlatformConnection:
        self.items[connection.id] = connection
        return connection

    def get_by_id(self, connection_id: str) -> Optional[PlatformConnection]:
        return self.items.get(connection_id)

    def get_by_platform_account(
        self, platform: str, account_external_id: str
    ) -> Optional[PlatformConnection]:
        for item in self.items.values():
            if (
                item.platform.value == platform
                and item.account_external_id == account_external_id
            ):
                return item
        return None

    def list_by_platform(
        self, platform: str, include_disconnected: bool = False
    ) -> List[PlatformConnection]:
        return [
            item
            for item in self.items.values()
            if item.platform.value == platform
            and (include_disconnected or item.is_active)
        ]

    def list_all(self, include_disconnected: bool = False) -> List[PlatformConnection]:
        return [
            item
            for item in self.items.values()
            if include_disconnected or item.is_active
        ]

    def count(self) -> int:
        return len(self.items)

    def delete(self, connection_id: str) -> bool:
        return self.items.pop(connection_id, None) is not None


class FakeChannelRepo(PlatformChannelRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, PlatformChannel] = {}

    def save(self, channel: PlatformChannel) -> PlatformChannel:
        self.items[channel.id] = channel
        return channel

    def get_by_id(self, channel_id: str) -> Optional[PlatformChannel]:
        return self.items.get(channel_id)

    def get_by_connection_external(
        self, connection_id: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        for channel in self.items.values():
            if (
                channel.platform_connection_id == connection_id
                and channel.channel_external_id == channel_external_id
            ):
                return channel
        return None

    def find_by_external_id(
        self, platform: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        for channel in self.items.values():
            if (
                channel.platform.value == platform
                and channel.channel_external_id == channel_external_id
            ):
                return channel
        return None

    def list_by_connection(self, connection_id: str) -> List[PlatformChannel]:
        return [
            item
            for item in self.items.values()
            if item.platform_connection_id == connection_id
        ]

    def list_enabled(self, platform: Optional[str] = None) -> List[PlatformChannel]:
        return [
            item
            for item in self.items.values()
            if item.is_enabled and (not platform or item.platform.value == platform)
        ]

    def set_enabled(
        self, channel_id: str, enabled: bool
    ) -> Optional[PlatformChannel]:
        channel = self.items.get(channel_id)
        if channel:
            channel.is_enabled = enabled
        return channel

    def count(self, enabled_only: bool = True) -> int:
        return len(
            [item for item in self.items.values() if item.is_enabled or not enabled_only]
        )

    def delete(self, channel_id: str) -> bool:
        return self.items.pop(channel_id, None) is not None


class FakeSelectionRepo(ChannelSelectionRepositoryPort):
    def __init__(self) -> None:
        self.selection = ChannelSelection()

    def get(self) -> ChannelSelection:
        return self.selection

    def save(self, selection: ChannelSelection) -> ChannelSelection:
        self.selection = selection
        return selection


class FakeTokenStorage(TokenStoragePort):
    def __init__(self) -> None:
        self.tokens: Dict[str, Dict[str, Optional[str]]] = {}

    def store_tokens(
        self, account_id: str, access_token: str, refresh_token: Optional[str] = None
    ) -> None:
        current = self.tokens.get(account_id, {})
        self.tokens[account_id] = {
            "access": access_token,
            "refresh": refresh_token if refresh_token is not None else current.get("refresh"),
        }

    def get_access_token(self, account_id: str) -> Optional[str]:
        return self.tokens.get(account_id, {}).get("access")

    def get_refresh_token(self, account_id: str) -> Optional[str]:
        return self.tokens.get(account_id, {}).get("refresh")

    def delete_tokens(self, account_id: str) -> None:
        self.tokens.pop(account_id, None)


class FakePublisher(YouTubePublisherPort):
    def __init__(self) -> None:
        self.requested_scopes: List[List[str]] = []
        self.exchange_tokens: Dict[str, Any] = {
            "access_token": "access_new",
            "refresh_token": "refresh_new",
            "expires_in": 3600,
            "scope": " ".join(BASE_SCOPES),
        }
        self.exchange_error: Optional[Exception] = None
        self.subject = "sub-1"

    def generate_auth_url(
        self,
        state: str,
        code_challenge: str,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        self.requested_scopes.append(list(scopes or []))
        return f"https://accounts.google.test/o/oauth2/auth?state={state}"

    def exchange_code_for_tokens(
        self, code: str, code_verifier: str, redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        if self.exchange_error:
            raise self.exchange_error
        return dict(self.exchange_tokens)

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {"access_token": "refreshed", "expires_in": 3600}

    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        return self.list_channel_profiles(access_token)[0]

    def list_channel_profiles(self, access_token: str) -> List[Dict[str, Any]]:
        return [{"channel_id": "UC_ONE", "channel_title": "Kanal Bir"}]

    def get_account_identity(self, access_token: str) -> Dict[str, Any]:
        return {"sub": self.subject, "name": "Test Hesap"}

    def initiate_resumable_upload(
        self,
        access_token: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str,
        privacy: str,
        total_bytes: int,
    ) -> str:
        return "https://upload.test/session"

    def upload_chunk(
        self,
        upload_session_uri: str,
        chunk_data: bytes,
        start_byte: int,
        total_bytes: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        return 200, {"id": "video_1"}

    def query_upload_status(self, upload_session_uri: str, total_bytes: int) -> int:
        return 0

    def upload_custom_thumbnail(
        self, access_token: str, video_id: str, thumbnail_path: str
    ) -> bool:
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _connection(
    connection_id: str = "conn_1",
    granted_scopes: Optional[List[str]] = None,
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
) -> PlatformConnection:
    return PlatformConnection(
        id=connection_id,
        platform=SocialPlatform.YOUTUBE,
        account_external_id="google:sub-1",
        account_display_name="Test Hesap",
        connection_status=status,
        token_reference=f"youtube.connection.{connection_id}",
        granted_scopes=list(granted_scopes or []),
    )


def _auth_flow():
    publisher = FakePublisher()
    connections = FakeConnectionRepo()
    generate = GenerateYouTubeAuthUrlUseCase(publisher=publisher, connection_repo=connections)
    complete = CompleteYouTubeAuthenticationUseCase(
        connection_repo=connections,
        channel_repo=FakeChannelRepo(),
        selection_repo=FakeSelectionRepo(),
        token_storage=FakeTokenStorage(),
        publisher=publisher,
    )
    return publisher, connections, generate, complete


# ---------------------------------------------------------------------------
# Capability model
# ---------------------------------------------------------------------------
def test_base_grant_is_identity_plus_channel_read_only():
    assert BASE_CAPABILITIES == (CAPABILITY_IDENTITY, CAPABILITY_CHANNEL_READ)
    assert scopes_for_capabilities([]) == BASE_SCOPES
    assert set(capabilities_for_scopes(BASE_SCOPES)) == set(BASE_CAPABILITIES)


def test_each_capability_maps_to_its_google_scope():
    assert CAPABILITY_SCOPE_MAP[CAPABILITY_ANALYTICS] == (SCOPE_ANALYTICS,)
    assert CAPABILITY_SCOPE_MAP[CAPABILITY_UPLOAD] == (SCOPE_UPLOAD,)
    assert CAPABILITY_SCOPE_MAP[CAPABILITY_COMMENTS] == (SCOPE_COMMENTS,)
    assert CAPABILITY_SCOPE_MAP[CAPABILITY_REVENUE] == (SCOPE_REVENUE,)


def test_unknown_capability_is_rejected():
    with pytest.raises(ValueError, match="Bilinmeyen yetenek"):
        normalize_capabilities(["upload", "delete_everything"])


def test_revenue_is_optional_and_never_requested_by_default():
    assert OPTIONAL_CAPABILITIES == (CAPABILITY_REVENUE,)
    assert SCOPE_REVENUE not in scopes_for_capabilities(["analytics", "upload", "comments"])


def test_merge_keeps_old_grants_and_drops_duplicates():
    merged = merge_capability_scopes(BASE_SCOPES + [SCOPE_UPLOAD], BASE_SCOPES)

    assert merged[: len(BASE_SCOPES) + 1] == BASE_SCOPES + [SCOPE_UPLOAD]
    assert len(merged) == len(set(merged))


# ---------------------------------------------------------------------------
# Authorization URL generation
# ---------------------------------------------------------------------------
def test_new_connection_requests_only_the_base_grant_by_default():
    publisher, _, generate, _ = _auth_flow()

    result = generate.execute()

    assert publisher.requested_scopes == [BASE_SCOPES]
    assert result.capabilities == list(BASE_CAPABILITIES)
    assert result.requested_scopes == BASE_SCOPES


def test_new_connection_adds_only_the_requested_capability_scope():
    publisher, _, generate, _ = _auth_flow()

    result = generate.execute(capabilities=["upload"])

    assert publisher.requested_scopes == [BASE_SCOPES + [SCOPE_UPLOAD]]
    assert result.capabilities == list(BASE_CAPABILITIES) + [CAPABILITY_UPLOAD]
    assert SCOPE_ANALYTICS not in result.requested_scopes
    assert SCOPE_COMMENTS not in result.requested_scopes


@pytest.mark.parametrize(
    "capability,scope",
    [
        (CAPABILITY_ANALYTICS, SCOPE_ANALYTICS),
        (CAPABILITY_COMMENTS, SCOPE_COMMENTS),
    ],
)
def test_analytics_and_comments_are_requested_only_on_demand(capability, scope):
    publisher, _, generate, _ = _auth_flow()

    result = generate.execute(capabilities=[capability])

    assert scope in result.requested_scopes
    other_extra_scopes = {SCOPE_ANALYTICS, SCOPE_UPLOAD, SCOPE_COMMENTS} - {scope}
    assert not (other_extra_scopes & set(result.requested_scopes))
    assert SCOPE_REVENUE not in result.requested_scopes


def test_auth_url_rejects_unknown_capability_before_creating_a_session():
    publisher, _, generate, _ = _auth_flow()

    with pytest.raises(ValueError, match="Bilinmeyen yetenek"):
        generate.execute(capabilities=["upload", "admin"])

    assert publisher.requested_scopes == []


def test_incremental_grant_never_narrows_an_existing_connection():
    publisher, connections, generate, _ = _auth_flow()
    existing_scopes = BASE_SCOPES + [SCOPE_ANALYTICS, SCOPE_UPLOAD]
    connections.save(_connection("conn_existing", existing_scopes))

    result = generate.execute(
        intent="reconnect", connection_id="conn_existing", capabilities=["comments"]
    )

    requested = publisher.requested_scopes[0]
    assert SCOPE_ANALYTICS in requested
    assert SCOPE_UPLOAD in requested
    assert SCOPE_COMMENTS in requested
    assert requested[: len(BASE_SCOPES)] == BASE_SCOPES
    assert set(result.capabilities) >= {
        CAPABILITY_ANALYTICS,
        CAPABILITY_UPLOAD,
        CAPABILITY_COMMENTS,
    }


def test_reconnect_requires_a_known_connection_id():
    _, _, generate, _ = _auth_flow()

    with pytest.raises(ValueError, match="connection_id"):
        generate.execute(intent="reconnect", capabilities=["upload"])


def test_reconnect_with_unknown_connection_is_rejected():
    _, _, generate, _ = _auth_flow()

    with pytest.raises(ChannelNotFoundException):
        generate.execute(intent="reconnect", connection_id="missing", capabilities=["upload"])


# ---------------------------------------------------------------------------
# Callback / token handling
# ---------------------------------------------------------------------------
def test_new_connection_records_what_google_actually_granted():
    publisher, connections, generate, complete = _auth_flow()
    publisher.exchange_tokens["scope"] = " ".join(BASE_SCOPES)  # fewer than requested

    state = generate.execute(capabilities=["upload"]).state
    response = complete.execute(code="code_1", state=state)

    saved = connections.get_by_id(response.id)
    assert saved is not None
    assert saved.granted_scopes == BASE_SCOPES
    assert has_capability(saved.granted_scopes, CAPABILITY_UPLOAD) is False


def test_new_connection_keeps_granted_capability_scope():
    publisher, connections, generate, complete = _auth_flow()
    publisher.exchange_tokens["scope"] = " ".join(BASE_SCOPES + [SCOPE_UPLOAD])

    response = complete.execute(code="code_2", state=generate.execute(capabilities=["upload"]).state)

    saved = connections.get_by_id(response.id)
    assert has_capability(saved.granted_scopes, CAPABILITY_UPLOAD) is True


def test_incremental_callback_preserves_previous_grants_and_refresh_token():
    publisher, connections, generate, complete = _auth_flow()
    existing = _connection("conn_keep", BASE_SCOPES + [SCOPE_ANALYTICS, SCOPE_UPLOAD])
    connections.save(existing)
    complete.token_storage.store_tokens(existing.token_reference, "access_old", "refresh_old")
    publisher.exchange_tokens = {
        "access_token": "access_incremental",
        "expires_in": 3600,
        # Google answered with fewer scopes and no new refresh token.
        "scope": " ".join(BASE_SCOPES),
    }

    response = complete.execute(
        code="code_3",
        state=generate.execute(
            intent="reconnect", connection_id="conn_keep", capabilities=["comments"]
        ).state,
    )

    saved = connections.get_by_id("conn_keep")
    assert saved.connection_status == ConnectionStatus.ACTIVE
    assert saved.id == response.id
    assert has_capability(saved.granted_scopes, CAPABILITY_ANALYTICS) is True
    assert has_capability(saved.granted_scopes, CAPABILITY_UPLOAD) is True
    assert complete.token_storage.get_refresh_token(saved.token_reference) == "refresh_old"


def test_failed_incremental_authorization_leaves_the_connection_untouched():
    publisher, connections, generate, complete = _auth_flow()
    existing = _connection("conn_safe", BASE_SCOPES + [SCOPE_ANALYTICS])
    connections.save(existing)
    complete.token_storage.store_tokens(existing.token_reference, "access_old", "refresh_old")
    publisher.exchange_error = AuthenticationRequiredException("denied")

    with pytest.raises(AuthenticationRequiredException):
        complete.execute(
            code="code_4",
            state=generate.execute(
                intent="reconnect", connection_id="conn_safe", capabilities=["upload"]
            ).state,
        )

    saved = connections.get_by_id("conn_safe")
    assert saved.connection_status == ConnectionStatus.ACTIVE
    assert saved.granted_scopes == existing.granted_scopes
    assert complete.token_storage.get_access_token(saved.token_reference) == "access_old"
    assert complete.token_storage.get_refresh_token(saved.token_reference) == "refresh_old"


def test_callback_state_is_single_use():
    publisher, _, generate, complete = _auth_flow()

    state = generate.execute().state
    complete.execute(code="code_5", state=state)

    with pytest.raises(DuplicateOAuthCallbackException):
        complete.execute(code="code_5", state=state)


def test_unknown_state_is_rejected_before_token_exchange():
    publisher, _, _, complete = _auth_flow()

    with pytest.raises(AuthenticationRequiredException):
        complete.execute(code="code_6", state="never-issued")


# ---------------------------------------------------------------------------
# Central resolver
# ---------------------------------------------------------------------------
def _statuses(service: YouTubeCapabilityService, connection: PlatformConnection):
    return {item.capability: item for item in service.resolve(connection)}


def test_resolver_reports_missing_capabilities_as_scope_required():
    connection = _connection("conn_base", BASE_SCOPES)
    statuses = _statuses(YouTubeCapabilityService(), connection)

    assert statuses[CAPABILITY_IDENTITY].status == CAPABILITY_STATUS_ACTIVE
    assert statuses[CAPABILITY_CHANNEL_READ].status == CAPABILITY_STATUS_ACTIVE
    for capability in (CAPABILITY_ANALYTICS, CAPABILITY_UPLOAD, CAPABILITY_COMMENTS):
        assert statuses[capability].status == CAPABILITY_STATUS_SCOPE_REQUIRED
    assert statuses[CAPABILITY_REVENUE].optional is True


def test_resolver_separates_api_not_enabled_from_missing_scope():
    connection = _connection("conn_analytics", BASE_SCOPES + [SCOPE_ANALYTICS])

    def provider(connection_id: str, capability: str) -> Optional[str]:
        if connection_id == "conn_analytics" and capability == CAPABILITY_ANALYTICS:
            return CAPABILITY_STATUS_API_NOT_ENABLED
        return None

    service = YouTubeCapabilityService(api_state_provider=provider)
    statuses = _statuses(service, connection)

    analytics = statuses[CAPABILITY_ANALYTICS]
    assert analytics.status == CAPABILITY_STATUS_API_NOT_ENABLED
    assert analytics.granted is True
    assert service.can(connection, CAPABILITY_ANALYTICS) is False
    assert has_capability(connection.granted_scopes, CAPABILITY_ANALYTICS) is True
    assert statuses[CAPABILITY_UPLOAD].status == CAPABILITY_STATUS_SCOPE_REQUIRED


def test_resolver_status_for_reauth_required_and_inactive_connections():
    service = YouTubeCapabilityService()
    reauth = _connection("conn_reauth", BASE_SCOPES, ConnectionStatus.REAUTH_REQUIRED)
    inactive = _connection("conn_off", BASE_SCOPES, ConnectionStatus.DISCONNECTED)

    assert (
        _statuses(service, reauth)[CAPABILITY_UPLOAD].status
        == CAPABILITY_STATUS_REAUTH_REQUIRED
    )
    assert (
        _statuses(service, inactive)[CAPABILITY_UPLOAD].status
        == CAPABILITY_STATUS_UNAVAILABLE
    )
    with pytest.raises(ConnectionInactiveException):
        service.require(inactive, CAPABILITY_UPLOAD)


@pytest.mark.parametrize(
    "capability,scope",
    [
        (CAPABILITY_UPLOAD, SCOPE_UPLOAD),
        (CAPABILITY_COMMENTS, SCOPE_COMMENTS),
        (CAPABILITY_ANALYTICS, SCOPE_ANALYTICS),
    ],
)
def test_require_rejects_missing_capability_with_actionable_error(capability, scope):
    service = YouTubeCapabilityService()
    connection = _connection("conn_gate", BASE_SCOPES)

    with pytest.raises(InsufficientScopeException) as excinfo:
        service.require(connection, capability)

    assert excinfo.value.required_scope == scope
    assert excinfo.value.capability == capability
    assert "korunur" in str(excinfo.value)


@pytest.mark.parametrize(
    "capability,scope",
    [
        (CAPABILITY_UPLOAD, SCOPE_UPLOAD),
        (CAPABILITY_COMMENTS, SCOPE_COMMENTS),
        (CAPABILITY_ANALYTICS, SCOPE_ANALYTICS),
    ],
)
def test_require_passes_when_the_scope_is_granted(capability, scope):
    service = YouTubeCapabilityService()
    connection = _connection("conn_gate", BASE_SCOPES + [scope])

    service.require(connection, capability)


def test_capabilities_never_leak_between_connections():
    service = YouTubeCapabilityService()
    first = _connection("conn_a", BASE_SCOPES + [SCOPE_ANALYTICS])
    second = _connection("conn_b", BASE_SCOPES)

    assert service.can(first, CAPABILITY_ANALYTICS) is True
    assert service.can(second, CAPABILITY_ANALYTICS) is False
    service.require(first, CAPABILITY_ANALYTICS)
    with pytest.raises(InsufficientScopeException):
        service.require(second, CAPABILITY_ANALYTICS)


# ---------------------------------------------------------------------------
# Analytics use case: scope vs API availability
# ---------------------------------------------------------------------------
class _AnalyticsGateway:
    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.bind_calls = 0

    def bind(self, context):
        self.bind_calls += 1
        reason = self.reason

        class _Analytics:
            def query(self, date_range, metrics=None, dimensions=None, include_revenue=False):
                return AnalyticsResult(
                    available=False,
                    reason=reason,
                    start_date=date_range.start_date.isoformat(),
                    end_date=date_range.end_date.isoformat(),
                )

        return SimpleNamespace(analytics=_Analytics())


class _AnalyticsResolver:
    def __init__(self, connection: PlatformConnection) -> None:
        self.connection = connection

    def resolve(self, channel_id=None):
        return SimpleNamespace(
            connection_id=self.connection.id,
            connection=self.connection,
            channel=SimpleNamespace(
                id="local_ch_1",
                platform=SocialPlatform.YOUTUBE,
                channel_external_id="UC_ONE",
                channel_name="Kanal Bir",
            ),
        )


def test_analytics_without_scope_returns_insufficient_scope_without_calling_google():
    connection = _connection("conn_no_scope", BASE_SCOPES)
    gateway = _AnalyticsGateway("api_not_enabled")
    service = YouTubeCapabilityService()
    use_case = GetChannelAnalyticsUseCase(
        resolver=_AnalyticsResolver(connection),
        gateway=gateway,
        capability_service=service,
        availability_registry=AnalyticsAvailabilityRegistry(),
    )

    result = use_case.execute(range_key="7", dimensions=["day"])

    assert result["analytics"].reason == "insufficient_scope"
    assert gateway.bind_calls == 0
    assert "yt-analytics.readonly" in result["explanation"]


def test_analytics_with_scope_reports_api_not_enabled_distinctly():
    connection = _connection("conn_api_off", BASE_SCOPES + [SCOPE_ANALYTICS])
    gateway = _AnalyticsGateway("api_not_enabled")
    registry = AnalyticsAvailabilityRegistry()
    service = YouTubeCapabilityService(
        api_state_provider=lambda connection_id, capability: registry.get(connection_id)
    )
    use_case = GetChannelAnalyticsUseCase(
        resolver=_AnalyticsResolver(connection),
        gateway=gateway,
        capability_service=service,
        availability_registry=registry,
    )

    result = use_case.execute(range_key="7", dimensions=["day"])

    assert result["analytics"].reason == "api_not_enabled"
    assert gateway.bind_calls == 1
    assert "Google Cloud Console" in result["explanation"]
    assert registry.get(connection.id) == CAPABILITY_STATUS_API_NOT_ENABLED
    assert service.can(connection, CAPABILITY_ANALYTICS) is False
    assert has_capability(connection.granted_scopes, CAPABILITY_ANALYTICS) is True
