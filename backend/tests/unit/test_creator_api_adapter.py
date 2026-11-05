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
    CreatorApiException,
    InsufficientScopeException,
)
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.publish_exceptions import QuotaExceededException
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


def test_unknown_analytics_metric_is_rejected_before_network_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("network should not be reached")

    api = build_api(handler)
    with pytest.raises(CreatorApiException):
        api.query(
            date_range=DateRange(date(2026, 10, 1), date(2026, 10, 2), "custom"),
            metrics=["views", "madeUpMetric"],
        )
