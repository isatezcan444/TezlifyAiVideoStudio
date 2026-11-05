"""Stage 6.2 real-YouTube read-only acceptance coverage.

These tests mirror the live acceptance run: a migrated legacy connection being
re-authorized by the real Google account, a second account staying isolated,
re-discovery not duplicating channels, Analytics failing closed when the API is
not enabled, and the dashboard/frontend surfacing the real reason.

No network call, Keychain write or real channel mutation happens here. HTTP
contracts are exercised through ``httpx.MockTransport`` in the unit adapter
suite; this module uses fake repositories and fake ports.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from tests.integration.test_multi_account_stage61 import (
    FakeChannelPort,
    FakePublishRepo,
    FakeScheduleRepo,
    Stack,
    build_stack,
    connect_two_accounts,
    profile,
    register_account,
)

from tezlify_studio.application.ports.analytics_port import AnalyticsPort
from tezlify_studio.application.ports.comment_port import CommentPort
from tezlify_studio.application.ports.creator_gateway_port import (
    CreatorGatewayPort,
    CreatorSession,
)
from tezlify_studio.application.use_cases.get_dashboard_use_case import (
    GetDashboardUseCase,
)
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import CreatorApiException
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    ChannelProfile,
)
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YOUTUBE_SCOPES
from tezlify_studio.infrastructure.youtube.youtube_creator_gateway import (
    YouTubeCreatorGateway,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_CONNECTION_ID = "legacy-acc-0"
LEGACY_CHANNEL_ID = "legacy-ch-0"
LEGACY_REFERENCE = "legacy-acc-0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def seed_legacy_connection(
    stack: Stack, external_channel_id: str = "UC_LEGACY", channel_name: str = "Legacy Channel"
) -> None:
    connection = PlatformConnection(
        id=LEGACY_CONNECTION_ID,
        platform=SocialPlatform.YOUTUBE,
        account_external_id=f"legacy:{external_channel_id}",
        account_display_name=channel_name,
        token_reference=LEGACY_REFERENCE,
    )
    stack.connections.save(connection)
    stack.channels.save(
        PlatformChannel(
            id=LEGACY_CHANNEL_ID,
            platform_connection_id=connection.id,
            platform=SocialPlatform.YOUTUBE,
            channel_external_id=external_channel_id,
            channel_name=channel_name,
            is_primary=True,
            is_enabled=True,
        )
    )
    selection = stack.selection.get()
    selection.select(LEGACY_CHANNEL_ID)
    stack.selection.save(selection)


class _FakeGateway(CreatorGatewayPort):
    def __init__(self, analytics: AnalyticsPort, profile_: Optional[ChannelProfile] = None) -> None:
        self.analytics = analytics
        self.profile = profile_
        self.bound: List[str] = []

    def list_platforms(self):
        return []

    def bind(self, context) -> CreatorSession:
        self.bound.append(context.external_channel_id)
        return CreatorSession(
            channel=FakeChannelPort(
                self.profile
                or ChannelProfile(channel_id=context.external_channel_id, title="channel")
            ),
            analytics=self.analytics,
            comments=_NoWriteComments(),
            access=ChannelAccess(
                platform=context.channel.platform,
                channel_id=context.channel_id,
                external_channel_id=context.external_channel_id,
                connection_id=context.connection_id,
                access_token="fake",
            ),
        )


class _NoWriteComments(CommentPort):
    def list_comments(self, video_id=None, max_results=25, page_token=None):
        return []

    def reply_to_comment(self, parent_comment_id: str, text: str):
        raise AssertionError("read-only acceptance must not write comments")

    def set_moderation_status(self, comment_id: str, status: str):
        raise AssertionError("read-only acceptance must not write comments")


class _UnavailableAnalytics(AnalyticsPort):
    def __init__(self, reason: str = "api_not_enabled") -> None:
        self.reason = reason
        self.calls = 0

    def query(
        self,
        date_range,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        self.calls += 1
        return AnalyticsResult(
            available=False,
            reason=self.reason,
            start_date=date_range.start_date.isoformat(),
            end_date=date_range.end_date.isoformat(),
            metrics=list(metrics or []),
            dimensions=list(dimensions or []),
        )


class _RaisingAnalytics(AnalyticsPort):
    def query(self, date_range, metrics=None, dimensions=None, include_revenue=False):
        raise CreatorApiException("Analytics isteği başarısız (HTTP 500)", status_code=500)


# ---------------------------------------------------------------------------
# OAuth scope contract
# ---------------------------------------------------------------------------
def test_oauth_scopes_are_least_privilege_and_cover_read_only_acceptance():
    scopes = set(YOUTUBE_SCOPES)

    assert "https://www.googleapis.com/auth/youtube" not in scopes, (
        "the broad youtube scope grants write access beyond what upload needs"
    )
    assert {
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    } == scopes


# ---------------------------------------------------------------------------
# Legacy re-authorization
# ---------------------------------------------------------------------------
def test_legacy_connection_is_upgraded_in_place_on_real_discovery():
    stack = build_stack()
    seed_legacy_connection(stack)
    register_account(
        stack.publisher,
        "code-real",
        "access-real",
        "refresh-real",
        "google-sub-real",
        "İsa Tezcan",
        [profile("UC_LEGACY", "İsa Tezcan", "@isatezcan7767")],
    )

    dto = stack.connect("code-real")

    # The migrated row is reused, not replaced: publish rows keep pointing at it.
    assert dto.id == LEGACY_CONNECTION_ID
    assert stack.connections.count() == 1
    assert stack.channels.count(enabled_only=False) == 1
    connection = stack.connections.get_by_id(LEGACY_CONNECTION_ID)
    assert connection.account_external_id == "google:google-sub-real"
    assert connection.account_display_name == "İsa Tezcan"
    assert connection.token_reference == LEGACY_REFERENCE

    channel = stack.channels.get_by_id(LEGACY_CHANNEL_ID)
    assert channel.channel_external_id == "UC_LEGACY"
    assert channel.channel_handle == "@isatezcan7767"
    assert channel.avatar_url == "https://img.test/UC_LEGACY.png"
    assert channel.uploads_playlist_id == "UU_UC_LEGACY"
    assert channel.is_enabled is True

    # Tokens stay under the migrated Keychain reference; no second account key.
    assert stack.tokens.tokens and set(stack.tokens.tokens) == {LEGACY_REFERENCE}
    assert stack.tokens.get_access_token(LEGACY_REFERENCE) == "access-real"
    assert stack.tokens.get_refresh_token(LEGACY_REFERENCE) == "refresh-real"


def test_new_real_account_does_not_touch_preserved_legacy_connection():
    stack = build_stack()
    seed_legacy_connection(stack, external_channel_id="UC_RESILIENCE", channel_name="Resilience Channel")
    register_account(
        stack.publisher,
        "code-real",
        "access-real",
        "refresh-real",
        "google-sub-real",
        "İsa Tezcan",
        [profile("UCtxeOcY7FyvxiWXgo3CQE4Q", "İsa Tezcan", "@isatezcan7767")],
    )

    dto = stack.connect("code-real")

    assert dto.id != LEGACY_CONNECTION_ID
    assert stack.connections.count() == 2
    legacy = stack.connections.get_by_id(LEGACY_CONNECTION_ID)
    legacy_channel = stack.channels.get_by_id(LEGACY_CHANNEL_ID)
    assert legacy.account_external_id == "legacy:UC_RESILIENCE"
    assert legacy.token_reference == LEGACY_REFERENCE
    assert legacy_channel.channel_external_id == "UC_RESILIENCE"
    assert legacy_channel.is_enabled is True

    new_connection = stack.connections.get_by_id(dto.id)
    assert new_connection.token_reference == f"youtube.connection.{dto.id}"
    assert stack.tokens.get_access_token(new_connection.token_reference) == "access-real"
    assert stack.tokens.get_access_token(LEGACY_REFERENCE) is None


# ---------------------------------------------------------------------------
# Channel discovery
# ---------------------------------------------------------------------------
def test_rediscovery_disables_removed_channel_without_deleting_history():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a1",
        "access-a1",
        "refresh-a1",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main"), profile("UC_A2", "Brand")],
    )
    first = stack.connect("code-a1")
    brand = next(item for item in first.channels if item.channel_external_id == "UC_A2")

    register_account(
        stack.publisher,
        "code-a2",
        "access-a2",
        "refresh-a2",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main")],
    )
    second = stack.connect("code-a2")

    assert stack.connections.count() == 1
    assert stack.channels.count(enabled_only=False) == 2
    assert {item.channel_external_id for item in second.channels} == {"UC_A1"}
    preserved = stack.channels.get_by_id(brand.id)
    assert preserved is not None
    assert preserved.channel_external_id == "UC_A2"
    assert preserved.is_enabled is False


def test_repeated_discovery_is_idempotent_for_channel_ids_and_names():
    stack = build_stack()
    profiles = [profile("UC_A1", "Main"), profile("UC_A2", "Brand")]
    register_account(
        stack.publisher, "code-1", "access-1", "refresh-1", "google-sub-a", "Account A", profiles
    )
    first = stack.connect("code-1")
    first_ids = sorted(item.id for item in first.channels)

    register_account(
        stack.publisher, "code-2", "access-2", "refresh-2", "google-sub-a", "Account A", profiles
    )
    second = stack.connect("code-2")

    assert sorted(item.id for item in second.channels) == first_ids
    assert stack.channels.count(enabled_only=False) == 2
    assert stack.connections.count() == 1


# ---------------------------------------------------------------------------
# Keychain / token reference isolation
# ---------------------------------------------------------------------------
def test_token_reference_is_connection_scoped_not_channel_scoped():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main")],
    )
    dto = stack.connect("code-a")
    connection = stack.connections.get_by_id(dto.id)
    channel = stack.channels.get_by_id(dto.channels[0].id)

    assert connection.token_reference == f"youtube.connection.{connection.id}"
    assert connection.token_reference != channel.channel_external_id
    assert connection.token_reference != channel.id
    # Exactly one Keychain account exists, and it is the connection reference.
    assert set(stack.tokens.tokens) == {connection.token_reference}


def test_two_accounts_keep_token_isolation_after_switch():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    conn_a = stack.connections.get_by_id(dto_a.id)
    conn_b = stack.connections.get_by_id(dto_b.id)

    assert stack.tokens.get_access_token(conn_a.token_reference) == "access-a"
    assert stack.tokens.get_access_token(conn_b.token_reference) == "access-b"
    assert stack.access.get_access(stack.resolver.resolve(dto_a.channels[0].id)).access_token == "access-a"
    assert stack.access.get_access(stack.resolver.resolve(dto_b.channels[0].id)).access_token == "access-b"

    stack.tokens.delete_tokens(conn_a.token_reference)
    assert stack.tokens.get_access_token(conn_b.token_reference) == "access-b"


def test_gateway_binds_one_channel_scoped_adapter_per_request():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    gateway = YouTubeCreatorGateway(stack.access)

    session_a = gateway.bind(stack.resolver.resolve(dto_a.channels[0].id))
    session_b = gateway.bind(stack.resolver.resolve(dto_b.channels[0].id))

    assert session_a is not session_b
    assert session_a.channel is not session_b.channel
    assert session_a.access.external_channel_id == "UC_A1"
    assert session_b.access.external_channel_id == "UC_B1"
    assert session_a.access.access_token == "access-a"
    assert session_b.access.access_token == "access-b"


# ---------------------------------------------------------------------------
# Dashboard and Analytics degradation
# ---------------------------------------------------------------------------
def _dashboard(stack: Stack, gateway: CreatorGatewayPort, channel_id: str):
    return GetDashboardUseCase(
        resolver=stack.resolver,
        gateway=gateway,
        publish_repo=FakePublishRepo(),
        schedule_repo=FakeScheduleRepo(),
    ).execute(range_key="28", channel_id=channel_id)


def test_dashboard_preserves_api_not_enabled_reason_without_fabricating_totals():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main")],
    )
    dto = stack.connect("code-a")
    analytics = _UnavailableAnalytics("api_not_enabled")
    gateway = _FakeGateway(
        analytics,
        ChannelProfile(channel_id="UC_A1", title="Main", subscriber_count=0, video_count=0, view_count=0),
    )

    snapshot = _dashboard(stack, gateway, dto.channels[0].id)

    assert snapshot.connected is True
    assert snapshot.analytics is not None
    assert snapshot.analytics.available is False
    assert snapshot.analytics.reason == "api_not_enabled"
    assert snapshot.analytics.totals == {}
    assert analytics.calls == 1
    assert snapshot.sources["views_over_time"] == "youtube_analytics_api"
    assert snapshot.sources["publish_history"] == "local_database"
    assert snapshot.warnings == []


def test_dashboard_reports_analytics_failure_as_warning_not_fake_data():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main")],
    )
    dto = stack.connect("code-a")
    gateway = _FakeGateway(_RaisingAnalytics())

    snapshot = _dashboard(stack, gateway, dto.channels[0].id)

    assert snapshot.analytics is None
    assert any("YouTube Analytics verisi alınamadı" in warning for warning in snapshot.warnings)
    assert snapshot.local_counts["total_publish_records"] == 0


def test_dashboard_does_not_reuse_previous_channel_state():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    gateway = _FakeGateway(_UnavailableAnalytics())

    snapshot_a = _dashboard(stack, gateway, dto_a.channels[0].id)
    snapshot_b = _dashboard(stack, gateway, dto_b.channels[0].id)

    assert gateway.bound == ["UC_A1", "UC_B1"]
    assert snapshot_a.channel_context["channel_id"] == dto_a.channels[0].id
    assert snapshot_b.channel_context["channel_id"] == dto_b.channels[0].id
    assert snapshot_a.channel_context["external_channel_id"] == "UC_A1"
    assert snapshot_b.channel_context["external_channel_id"] == "UC_B1"


# ---------------------------------------------------------------------------
# Frontend contract for the real reason
# ---------------------------------------------------------------------------
def test_dashboard_explains_api_not_enabled_instead_of_blaming_permissions():
    source = (REPO_ROOT / "frontend/src/pages/DashboardPage.tsx").read_text()

    assert "api_not_enabled" in source
    assert "Google Cloud Console" in source
    assert "Analitik verisi kullanılamıyor. Bağlı Hesaplar sayfasından yetkileri genişletebilirsiniz." not in source
    assert "analyticsReasonDetail(analytics?.reason)" in source
    assert "analyticsReasonLabel(analytics?.reason)" in source
