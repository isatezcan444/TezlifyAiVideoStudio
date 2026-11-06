"""YouTube adapter tests against a mocked HTTP transport.

No real YouTube call is made: every request goes through httpx.MockTransport, so
the suite stays read-only and deterministic.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable, Dict, Optional

import httpx
import pytest

from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelBindingMismatchException,
    CreatorApiException,
    InsufficientScopeException,
)
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
    QuotaExceededException,
)
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.creator_models import DateRange
from tezlify_studio.infrastructure.youtube.youtube_creator_api import (
    YouTubeCreatorApi,
    parse_iso_duration,
)


CHANNEL_ACCESS = ChannelAccess(
    platform=SocialPlatform.YOUTUBE,
    channel_id="local_ch_1",
    external_channel_id="UC_REAL",
    connection_id="conn_1",
    access_token="mock_access_token",
)


def build_api(handler: Callable[[httpx.Request], httpx.Response]) -> YouTubeCreatorApi:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeCreatorApi(CHANNEL_ACCESS, client=client)


CHANNEL = {
    "items": [
        {
            "id": "UC_REAL",
            "snippet": {"title": "Kanal", "description": "Aciklama"},
            "statistics": {
                "subscriberCount": "1234",
                "videoCount": "12",
                "viewCount": "98765",
                "hiddenSubscriberCount": False,
            },
            "contentDetails": {"relatedPlaylists": {"uploads": "UU_REAL"}},
        }
    ]
}

VIDEOS = {
    "items": [
        {
            "id": "vid_1",
            "snippet": {
                "title": "Ilk video",
                "description": "Aciklama",
                "publishedAt": "2026-10-01T10:00:00Z",
                "tags": ["a", "b"],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
            "statistics": {"viewCount": "100", "likeCount": "10", "commentCount": "2"},
            "contentDetails": {"duration": "PT1M2S"},
        }
    ]
}


def test_parse_iso_duration_handles_hours_minutes_seconds() -> None:
    assert parse_iso_duration("PT1H2M3S") == 3723
    assert parse_iso_duration("PT45S") == 45
    assert parse_iso_duration("bad") is None


def test_list_videos_maps_playlist_items_into_channel_videos() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer mock_access_token"
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [{"contentDetails": {"videoId": "vid_1"}}],
                    "nextPageToken": "next",
                    "pageInfo": {"totalResults": 1},
                },
            )
        if request.url.path.endswith("/videos"):
            return httpx.Response(200, json=VIDEOS)
        raise AssertionError(f"unexpected URL {request.url}")

    api = build_api(handler)
    result = api.list_videos(max_results=5)

    assert result["next_page_token"] == "next"
    assert result["total_results"] == 1
    video = result["items"][0]
    assert video.video_id == "vid_1"
    assert video.duration_seconds == 62
    assert video.privacy_status == "public"
    assert video.view_count == 100
    assert video.category_id == "22"


def test_analytics_uses_dimensionless_query_for_period_totals() -> None:
    calls: list[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert "youtubeanalytics.googleapis.com" in str(request.url)
        calls.append(dict(request.url.params))
        metric_headers = [
            {"name": "views", "columnType": "METRIC"},
            {"name": "averageViewDuration", "columnType": "METRIC"},
            {"name": "estimatedMinutesWatched", "columnType": "METRIC"},
        ]
        if "dimensions" in request.url.params:
            headers = [{"name": "day", "columnType": "DIMENSION"}, *metric_headers]
            rows = [["2026-10-01", 60, 30, 5], ["2026-10-02", 40, 90, 8]]
        else:
            # A dimension-less report has metric columns only. Its single row is
            # YouTube's authoritative total (averageViewDuration 55 is not the
            # client-side mean of 30 and 90).
            headers = metric_headers
            rows = [[100, 55, 13]]
        return httpx.Response(
            200, json={"columnHeaders": headers, "rows": rows}
        )

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
        metrics=["views", "averageViewDuration", "estimatedMinutesWatched"],
        dimensions=["day"],
    )

    assert result.available is True
    assert result.totals == {
        "views": 100.0,
        "averageViewDuration": 55.0,
        "estimatedMinutesWatched": 13.0,
    }
    assert [row.dimensions["day"] for row in result.rows] == ["2026-10-01", "2026-10-02"]
    assert calls[0]["ids"] == "channel==UC_REAL"
    assert "dimensions" not in calls[0]
    assert calls[1]["dimensions"] == "day"


def test_analytics_missing_scope_degrades_instead_of_fabricating() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "Request had insufficient authentication scopes.",
                    "errors": [{"reason": "insufficientPermissions"}],
                }
            },
        )

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
    )

    assert result.available is False
    assert result.reason == "insufficient_scope"
    assert result.totals == {}
    assert result.rows == []


def test_quota_error_surfaces_as_quota_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "Quota exceeded",
                    "errors": [{"reason": "quotaExceeded"}],
                }
            },
        )

    api = build_api(handler)
    with pytest.raises(QuotaExceededException):
        api.get_channel()


def test_comments_disabled_403_is_explained_without_google_markup() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200, json={"items": [{"contentDetails": {"videoId": "vid_1"}}]}
            )
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": (
                        'The video identified by the <code><a href="/youtube/data/'
                        'reference/rest/v3/commentThreads/list#videoId">videoId</a>'
                        "</code> parameter has disabled comments."
                    ),
                    "errors": [{"reason": "commentsDisabled"}],
                }
            },
        )

    api = build_api(handler)
    with pytest.raises(CreatorApiException) as exc:
        api.list_comments(video_id="vid_1")

    assert "yorumlar kapalı" in str(exc.value).lower()
    assert "<code>" not in str(exc.value)
    assert "videoId" not in str(exc.value)


def test_generic_forbidden_message_never_contains_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "Denied by <b>policy</b> for this &amp; that reason.",
                    "errors": [{"reason": "forbidden"}],
                }
            },
        )

    api = build_api(handler)
    with pytest.raises(CreatorApiException) as exc:
        api.get_channel()

    message = str(exc.value)
    assert "<b>" not in message
    assert "Denied by policy for this & that reason." in message


def test_analytics_api_not_enabled_returns_structured_reason() -> None:
    """A disabled Analytics API is a project setting, not a permission problem."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": (
                        "YouTube Analytics API has not been used in project 123 "
                        "before or it is disabled."
                    ),
                    "errors": [{"reason": "accessNotConfigured"}],
                }
            },
        )

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 9), date(2026, 11, 5), "28"),
    )

    assert result.available is False
    assert result.reason == "api_not_enabled"
    assert result.totals == {}
    assert result.rows == []
    assert result.start_date == "2026-10-09"
    assert result.end_date == "2026-11-05"


def test_analytics_401_requires_reauthentication_instead_of_empty_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid Credentials"}})

    api = build_api(handler)
    with pytest.raises(AuthenticationRequiredException):
        api.query(
            date_range=DateRange(date(2026, 10, 9), date(2026, 11, 5), "28"),
        )


def test_get_channel_maps_real_discovery_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id"] == "UC_REAL"
        assert "mine" not in request.url.params
        return httpx.Response(200, json=CHANNEL)

    api = build_api(handler)
    channel = api.get_channel()

    assert channel.channel_id == "UC_REAL"
    assert channel.title == "Kanal"
    assert channel.description == "Aciklama"
    assert channel.subscriber_count == 1234
    assert channel.video_count == 12
    assert channel.view_count == 98765
    assert channel.hidden_subscriber_count is False
    assert channel.uploads_playlist_id == "UU_REAL"


def test_get_channel_without_items_is_a_binding_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    api = build_api(handler)
    with pytest.raises(ChannelBindingMismatchException):
        api.get_channel()


def test_update_video_sends_snippet_and_only_requested_privacy() -> None:
    captured: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200, json={"items": [{"contentDetails": {"videoId": "vid_1"}}]}
            )
        if request.method == "GET":
            return httpx.Response(200, json=VIDEOS)
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                **VIDEOS["items"][0],
                "snippet": {**VIDEOS["items"][0]["snippet"], "title": "Yeni baslik"},
            },
        )

    api = build_api(handler)
    updated = api.update_video("vid_1", {"title": "Yeni baslik"})

    assert updated.title == "Yeni baslik"
    assert captured["id"] == "vid_1"
    assert captured["snippet"]["title"] == "Yeni baslik"
    assert captured["snippet"]["description"] == "Aciklama"
    assert "status" not in captured


def test_comments_are_mapped_from_threads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {
                            "totalReplyCount": 3,
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {
                                    "videoId": "vid_1",
                                    "authorDisplayName": "Izleyici",
                                    "textOriginal": "Harika",
                                    "likeCount": 4,
                                    "publishedAt": "2026-10-02T10:00:00Z",
                                },
                            },
                        }
                    }
                ]
            },
        )

    api = build_api(handler)
    comments = api.list_comments()

    assert len(comments) == 1
    assert comments[0].comment_id == "c1"
    assert comments[0].text == "Harika"
    assert comments[0].total_reply_count == 3


def test_http_400_becomes_creator_api_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    api = build_api(handler)
    with pytest.raises(CreatorApiException):
        api.get_video("video_x")


def test_traffic_source_dimension_uses_google_identifier_and_keeps_public_key() -> None:
    calls: list[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if "dimensions" in request.url.params:
            headers = [
                {"name": "insightTrafficSourceType", "columnType": "DIMENSION"},
                {"name": "views", "columnType": "METRIC"},
            ]
            rows = [["YT_SEARCH", 10]]
        else:
            headers = [{"name": "views", "columnType": "METRIC"}]
            rows = [[10]]
        return httpx.Response(200, json={"columnHeaders": headers, "rows": rows})

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
        metrics=["views"],
        dimensions=["trafficSourceType"],
    )

    assert calls[1]["dimensions"] == "insightTrafficSourceType"
    assert result.rows[0].dimensions == {"trafficSourceType": "YT_SEARCH"}


def test_reports_without_subscriber_metrics_drop_them_from_dimension_query() -> None:
    calls: list[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if "dimensions" in request.url.params:
            headers = [
                {"name": "deviceType", "columnType": "DIMENSION"},
                {"name": "views", "columnType": "METRIC"},
            ]
            rows = [["MOBILE", 10]]
        else:
            headers = [
                {"name": "views", "columnType": "METRIC"},
                {"name": "subscribersGained", "columnType": "METRIC"},
                {"name": "subscribersLost", "columnType": "METRIC"},
            ]
            rows = [[10, 1, 2]]
        return httpx.Response(200, json={"columnHeaders": headers, "rows": rows})

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
        metrics=["views", "subscribersGained", "subscribersLost"],
        dimensions=["deviceType"],
    )

    # Period totals stay complete; only the grouped report drops unsupported metrics.
    assert "subscribersGained" in calls[0]["metrics"]
    assert calls[1]["metrics"] == "views"
    assert result.totals == {"views": 10.0, "subscribersGained": 1.0, "subscribersLost": 2.0}
    assert result.rows[0].metrics == {"views": 10.0}


def test_top_videos_dimension_sends_sort_and_max_results() -> None:
    calls: list[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if "dimensions" in request.url.params:
            headers = [
                {"name": "video", "columnType": "DIMENSION"},
                {"name": "views", "columnType": "METRIC"},
            ]
            rows = [["vid_1", 10]]
        else:
            headers = [{"name": "views", "columnType": "METRIC"}]
            rows = [[10]]
        return httpx.Response(200, json={"columnHeaders": headers, "rows": rows})

    api = build_api(handler)
    api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
        metrics=["views"],
        dimensions=["video"],
    )

    assert calls[1]["dimensions"] == "video"
    assert calls[1]["sort"] == "-views"
    assert calls[1]["maxResults"] == "25"


def test_revenue_includes_daily_trend_and_top_videos() -> None:
    calls: list[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append(params)
        metrics = params.get("metrics", "")
        if "estimatedRevenue" in metrics:
            if params.get("dimensions") == "video":
                headers = [
                    {"name": "video", "columnType": "DIMENSION"},
                    {"name": "estimatedRevenue", "columnType": "METRIC"},
                    {"name": "estimatedAdRevenue", "columnType": "METRIC"},
                    {"name": "views", "columnType": "METRIC"},
                    {"name": "estimatedMinutesWatched", "columnType": "METRIC"},
                    {"name": "averageViewDuration", "columnType": "METRIC"},
                ]
                rows = [["vid_1", 1.5, 1.2, 100, 20, 12]]
            elif params.get("dimensions") == "day":
                headers = [
                    {"name": "day", "columnType": "DIMENSION"},
                    {"name": "estimatedRevenue", "columnType": "METRIC"},
                    {"name": "estimatedAdRevenue", "columnType": "METRIC"},
                ]
                rows = [["2026-10-01", 1.0, 0.8], ["2026-10-02", 0.5, 0.4]]
            else:
                headers = [
                    {"name": "estimatedRevenue", "columnType": "METRIC"},
                    {"name": "estimatedAdRevenue", "columnType": "METRIC"},
                ]
                rows = [[1.5, 1.2]]
        elif params.get("dimensions") == "day":
            headers = [
                {"name": "day", "columnType": "DIMENSION"},
                {"name": "views", "columnType": "METRIC"},
            ]
            rows = [["2026-10-01", 60], ["2026-10-02", 40]]
        else:
            headers = [{"name": "views", "columnType": "METRIC"}]
            rows = [[100]]
        return httpx.Response(200, json={"columnHeaders": headers, "rows": rows})

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
        metrics=["views"],
        dimensions=["day"],
        include_revenue=True,
    )

    assert result.available is True
    revenue = result.revenue or {}
    assert revenue["available"] is True
    assert revenue["amount"] == 1.5
    assert revenue["ad_revenue"] == 1.2
    assert [row.dimensions["day"] for row in revenue["daily"]] == ["2026-10-01", "2026-10-02"]
    assert revenue["top_videos"][0].dimensions["video"] == "vid_1"
    assert revenue["top_videos"][0].metrics["estimatedRevenue"] == 1.5
    assert revenue["top_videos"][0].metrics["estimatedMinutesWatched"] == 20
    assert revenue["top_videos"][0].metrics["averageViewDuration"] == 12
    video_call = next(call for call in calls if call.get("dimensions") == "video")
    assert video_call["sort"] == "-estimatedRevenue"
    assert video_call["maxResults"] == "25"
    assert "estimatedMinutesWatched" in video_call["metrics"]
    assert "averageViewDuration" in video_call["metrics"]


def test_revenue_scope_missing_keeps_analytics_without_fabricating_revenue() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "estimatedRevenue" in request.url.params.get("metrics", ""):
            return httpx.Response(
                403,
                json={
                    "error": {
                        "message": "Request had insufficient authentication scopes.",
                        "errors": [{"reason": "insufficientPermissions"}],
                    }
                },
            )
        headers = [{"name": "views", "columnType": "METRIC"}]
        return httpx.Response(200, json={"columnHeaders": headers, "rows": [[10]]})

    api = build_api(handler)
    result = api.query(
        date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
        metrics=["views"],
        include_revenue=True,
    )

    assert result.available is True
    assert result.revenue is not None
    assert result.revenue["available"] is False
    assert result.revenue["reason"] == "insufficient_scope"
    assert "amount" not in result.revenue


def test_unknown_analytics_metric_is_rejected_before_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("network should not be reached")

    api = build_api(handler)
    with pytest.raises(CreatorApiException):
        api.query(
            date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
            metrics=["views", "madeUpMetric"],
        )
