"""Stage 6.3 contracts: OAuth capability scopes, incremental grants, Analytics
reason text and the public-only video count semantics.

No real Google API call is made; HTTP is mocked with httpx.MockTransport.
"""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx

from tezlify_studio.application.use_cases.get_channel_analytics_use_case import (
    GetChannelAnalyticsUseCase,
)
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.creator_models import AnalyticsResult
from tezlify_studio.infrastructure.media.youtube_api_client_impl import (
    YouTubeApiClientImpl,
)
from tezlify_studio.infrastructure.youtube.youtube_creator_api import (
    BASE_SCOPES,
    OPTIONAL_SCOPES,
    SCOPE_ANALYTICS,
    SCOPE_CAPABILITIES,
    SCOPE_REVENUE,
    YOUTUBE_SCOPES,
    YouTubeCreatorApi,
)

CHANNEL_ACCESS = ChannelAccess(
    platform=SocialPlatform.YOUTUBE,
    channel_id="local_ch_1",
    external_channel_id="UC_REAL",
    connection_id="conn_1",
    access_token="mock_access_token",
)


# ---------------------------------------------------------------------------
# OAuth capability scopes
# ---------------------------------------------------------------------------
def test_default_consent_is_the_union_of_explicit_capability_scopes():
    grouped = [scope for scopes in SCOPE_CAPABILITIES.values() for scope in scopes]

    assert grouped == YOUTUBE_SCOPES
    assert len(grouped) == len(set(grouped))
    assert "https://www.googleapis.com/auth/youtube" not in YOUTUBE_SCOPES


def test_revenue_scope_is_opt_in_and_not_part_of_default_consent():
    assert SCOPE_REVENUE not in YOUTUBE_SCOPES
    assert OPTIONAL_SCOPES["revenue"] == SCOPE_REVENUE
    assert "yt-analytics-monetary.readonly" not in " ".join(YOUTUBE_SCOPES)


def test_auth_url_enables_incremental_authorization_and_defaults_to_base_scopes():
    client = YouTubeApiClientImpl(
        client_id="test_client_id",
        redirect_uri="http://127.0.0.1:54321/oauth2callback",
    )
    query = parse_qs(
        urlparse(client.generate_auth_url(state="state", code_challenge="challenge")).query
    )

    assert query["include_granted_scopes"] == ["true"]
    assert query["scope"] == [" ".join(BASE_SCOPES)]


def test_auth_url_accepts_an_explicit_incremental_scope_set():
    client = YouTubeApiClientImpl(
        client_id="test_client_id",
        redirect_uri="http://127.0.0.1:54321/oauth2callback",
    )
    query = parse_qs(
        urlparse(
            client.generate_auth_url(
                state="state", code_challenge="challenge", scopes=list(YOUTUBE_SCOPES)
            )
        ).query
    )

    assert query["scope"] == [" ".join(YOUTUBE_SCOPES)]


# ---------------------------------------------------------------------------
# Analytics failure explanations
# ---------------------------------------------------------------------------
class _AnalyticsStub:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def query(self, date_range, metrics=None, dimensions=None, include_revenue=False):
        return AnalyticsResult(
            available=False,
            reason=self.reason,
            start_date=date_range.start_date.isoformat(),
            end_date=date_range.end_date.isoformat(),
        )


class _ResolverStub:
    def resolve(self, channel_id=None):
        return SimpleNamespace(
            connection_id="conn_1",
            channel=SimpleNamespace(
                id="local_ch_1",
                platform=SocialPlatform.YOUTUBE,
                channel_external_id="UC_REAL",
                channel_name="Kanal",
            ),
            connection=SimpleNamespace(
                id="conn_1",
                connection_status=SimpleNamespace(value="active"),
                granted_scopes=[SCOPE_ANALYTICS],
            ),
        )


class _GatewayStub:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def bind(self, context):
        return SimpleNamespace(analytics=_AnalyticsStub(self.reason))


def _run_analytics(reason: str):
    use_case = GetChannelAnalyticsUseCase(
        resolver=_ResolverStub(),
        gateway=_GatewayStub(reason),
    )
    return use_case.execute(range_key="7", dimensions=["day"])


def test_forbidden_analytics_reason_is_explained():
    result = _run_analytics("forbidden")

    assert result["analytics"].available is False
    assert "reddedildi" in result["explanation"]


def test_api_error_analytics_reason_is_explained():
    result = _run_analytics("api_error")

    assert result["analytics"].available is False
    assert "beklenmeyen bir hata" in result["explanation"]


def test_unknown_analytics_reason_falls_back_to_generic_text():
    result = _run_analytics("something_new")

    assert result["explanation"] == "Analitik verisi şu anda kullanılamıyor."


# ---------------------------------------------------------------------------
# Public-only video count vs uploads playlist
# ---------------------------------------------------------------------------
def test_channel_video_count_and_uploads_playlist_are_distinct_signals():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UC_REAL",
                            "snippet": {"title": "Kanal"},
                            "statistics": {
                                "subscriberCount": "10",
                                "videoCount": "0",
                                "viewCount": "100",
                            },
                            "contentDetails": {
                                "relatedPlaylists": {"uploads": "UU_REAL"}
                            },
                        }
                    ]
                },
            )
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": "public_1"}},
                        {"contentDetails": {"videoId": "private_1"}},
                    ],
                    "pageInfo": {"totalResults": 2},
                },
            )
        if request.url.path.endswith("/videos"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "public_1",
                            "snippet": {"title": "Herkese açık"},
                            "status": {"privacyStatus": "public"},
                        },
                        {
                            "id": "private_1",
                            "snippet": {"title": "Özel"},
                            "status": {"privacyStatus": "private"},
                        },
                    ]
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    api = YouTubeCreatorApi(
        CHANNEL_ACCESS,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert api.get_channel().video_count == 0

    listing = api.list_videos(max_results=50)
    assert listing["total_results"] == 2
    assert {item.video_id for item in listing["items"]} == {"public_1", "private_1"}
    assert {item.privacy_status for item in listing["items"]} == {
        "public",
        "private",
    }
