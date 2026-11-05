"""Creator-management API contract tests.

All YouTube ports are fakes: no request leaves the process, so the suite is
read-only with respect to any real channel.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from tezlify_studio.application.use_cases.get_channel_analytics_use_case import (
    GetChannelAnalyticsUseCase,
)
from tezlify_studio.application.use_cases.get_channel_overview_use_case import (
    GetChannelOverviewUseCase,
)
from tezlify_studio.application.use_cases.get_channel_video_use_case import (
    GetChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.list_channel_playlists_use_case import (
    ListChannelPlaylistsUseCase,
)
from tezlify_studio.application.use_cases.list_channel_videos_use_case import (
    ListChannelVideosUseCase,
)
from tezlify_studio.application.use_cases.list_comments_use_case import ListCommentsUseCase
from tezlify_studio.application.use_cases.list_platforms_use_case import ListPlatformsUseCase
from tezlify_studio.application.use_cases.list_video_categories_use_case import (
    ListVideoCategoriesUseCase,
)
from tezlify_studio.application.use_cases.reply_to_comment_use_case import (
    ReplyToCommentUseCase,
)
from tezlify_studio.application.use_cases.set_comment_moderation_use_case import (
    SetCommentModerationUseCase,
)
from tezlify_studio.application.use_cases.update_channel_video_use_case import (
    UpdateChannelVideoUseCase,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorSession
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import InsufficientScopeException
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    AnalyticsRow,
    ChannelPlaylist,
    ChannelProfile,
    ChannelVideo,
    DateRange,
    PlatformDescriptor,
    VideoComment,
)
from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies import container


class FakeChannelPort:
    def __init__(self) -> None:
        self.updates: List[Dict[str, Any]] = []

    def get_channel(self) -> ChannelProfile:
        return ChannelProfile(
            channel_id="UC_FAKE",
            title="Test Kanalı",
            subscriber_count=1500,
            video_count=4,
            view_count=25000,
        )

    def list_videos(
        self, max_results: int = 25, page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "items": [
                ChannelVideo(
                    video_id="v1",
                    title="Bölüm 1",
                    privacy_status="public",
                    upload_status="processed",
                    duration_seconds=90,
                )
            ],
            "next_page_token": None,
            "total_results": 1,
        }

    def get_video(self, video_id: str) -> ChannelVideo:
        return ChannelVideo(video_id=video_id, title="Bölüm 1")

    def update_video(self, video_id: str, changes: Dict[str, Any]) -> ChannelVideo:
        self.updates.append(changes)
        return ChannelVideo(
            video_id=video_id,
            title=changes.get("title", "Bölüm 1"),
            privacy_status=changes.get("privacy_status", "public"),
        )

    def list_playlists(self, max_results: int = 25) -> List[ChannelPlaylist]:
        return [ChannelPlaylist(playlist_id="pl1", title="Seri", item_count=3)]

    def list_video_categories(self) -> List[Dict[str, str]]:
        return [{"id": "22", "title": "People & Blogs"}]


class FakeAnalyticsPort:
    def __init__(self) -> None:
        self.available = True

    def query(
        self,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        if not self.available:
            return AnalyticsResult(
                available=False,
                reason="insufficient_scope",
                start_date=date_range.start_date.isoformat(),
                end_date=date_range.end_date.isoformat(),
            )
        return AnalyticsResult(
            available=True,
            start_date=date_range.start_date.isoformat(),
            end_date=date_range.end_date.isoformat(),
            metrics=list(metrics or []),
            dimensions=list(dimensions or []),
            totals={"views": 1000.0, "averageViewDuration": 61.0},
            rows=[
                AnalyticsRow(
                    dimensions={"day": "2026-10-01"},
                    metrics={"views": 1000.0, "averageViewDuration": 61.0},
                )
            ],
            revenue=None,
        )


class FakeCatalogPort:
    def list_platforms(self) -> List[PlatformDescriptor]:
        return [
            PlatformDescriptor(
                id="youtube",
                display_name="YouTube",
                implemented=True,
                capabilities={"analytics": True},
            )
        ]


class FakeCommentPort:
    def list_comments(
        self,
        video_id: Optional[str] = None,
        max_results: int = 25,
        page_token: Optional[str] = None,
    ) -> List[VideoComment]:
        return [
            VideoComment(
                comment_id="c1",
                video_id=video_id or "v1",
                author="İzleyici",
                text="Güzel video",
            )
        ]

    def reply_to_comment(self, parent_comment_id: str, text: str) -> VideoComment:
        return VideoComment(
            comment_id="c2",
            video_id="v1",
            author="Kanal",
            text=text,
        )

    def set_moderation_status(self, comment_id: str, status: str) -> VideoComment:
        return VideoComment(
            comment_id=comment_id,
            video_id="v1",
            author="İzleyici",
            text="",
            moderation_status=status,
        )


class FakeResolver:
    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        return ChannelContext(
            channel=PlatformChannel(
                id="local_ch_1",
                platform_connection_id="conn_1",
                platform=SocialPlatform.YOUTUBE,
                channel_external_id="UC_FAKE",
                channel_name="Test Kanalı",
            ),
            connection=PlatformConnection(
                id="conn_1",
                platform=SocialPlatform.YOUTUBE,
                account_external_id="google_1",
                account_display_name="Test Hesabı",
            ),
        )


class FakeGateway:
    def __init__(self, channel: FakeChannelPort, analytics: FakeAnalyticsPort, comments: FakeCommentPort) -> None:
        self.channel = channel
        self.analytics = analytics
        self.comments = comments

    def list_platforms(self) -> List[PlatformDescriptor]:
        return FakeCatalogPort().list_platforms()

    def bind(self, context: ChannelContext) -> CreatorSession:
        return CreatorSession(
            channel=self.channel,
            analytics=self.analytics,
            comments=self.comments,
            access=ChannelAccess(
                platform=SocialPlatform.YOUTUBE,
                channel_id=context.channel_id,
                external_channel_id=context.external_channel_id,
                connection_id=context.connection_id,
                access_token="mock_access_token",
            ),
        )


@pytest.fixture()
def analytics_port() -> FakeAnalyticsPort:
    return FakeAnalyticsPort()


@pytest.fixture()
def client(analytics_port: FakeAnalyticsPort) -> TestClient:
    channel = FakeChannelPort()
    comments = FakeCommentPort()
    resolver = FakeResolver()
    gateway = FakeGateway(channel, analytics_port, comments)

    overrides = {
        container.get_list_platforms_use_case: lambda: ListPlatformsUseCase(FakeCatalogPort()),
        container.get_channel_overview_use_case: lambda: GetChannelOverviewUseCase(resolver, gateway),
        container.get_list_channel_videos_use_case: lambda: ListChannelVideosUseCase(resolver, gateway),
        container.get_channel_video_use_case: lambda: GetChannelVideoUseCase(resolver, gateway),
        container.get_update_channel_video_use_case: lambda: UpdateChannelVideoUseCase(resolver, gateway),
        container.get_list_channel_playlists_use_case: lambda: ListChannelPlaylistsUseCase(resolver, gateway),
        container.get_list_video_categories_use_case: lambda: ListVideoCategoriesUseCase(resolver, gateway),
        container.get_channel_analytics_use_case: lambda: GetChannelAnalyticsUseCase(
            resolver, gateway, max_range_days=365
        ),
        container.get_list_comments_use_case: lambda: ListCommentsUseCase(resolver, gateway),
        container.get_reply_to_comment_use_case: lambda: ReplyToCommentUseCase(resolver, gateway),
        container.get_set_comment_moderation_use_case: lambda: SetCommentModerationUseCase(
            resolver, gateway
        ),
    }
    app.dependency_overrides.update(overrides)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_platforms_advertise_only_youtube(client: TestClient) -> None:
    response = client.get("/api/v1/platforms")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == ["youtube"]
    assert body[0]["implemented"] is True


def test_channel_overview_and_videos_use_creator_ports(client: TestClient) -> None:
    overview = client.get("/api/v1/channels/youtube/overview")
    assert overview.status_code == 200
    assert overview.json()["channel"]["title"] == "Test Kanalı"
    assert overview.json()["playlists"][0]["playlist_id"] == "pl1"

    videos = client.get("/api/v1/channels/youtube/videos", params={"max_results": 5})
    assert videos.status_code == 200
    assert videos.json()["items"][0]["video_id"] == "v1"
    assert videos.json()["source"] == "youtube_data_api"


def test_metadata_update_requires_explicit_fields(client: TestClient) -> None:
    empty = client.patch("/api/v1/channels/youtube/videos/v1", json={})
    assert empty.status_code == 400

    invalid_privacy = client.patch(
        "/api/v1/channels/youtube/videos/v1", json={"privacy_status": "secret"}
    )
    assert invalid_privacy.status_code == 422

    updated = client.patch(
        "/api/v1/channels/youtube/videos/v1",
        json={"title": "Yeni başlık", "privacy_status": "unlisted"},
    )
    assert updated.status_code == 200
    assert updated.json()["video"]["title"] == "Yeni başlık"
    assert updated.json()["video"]["privacy_status"] == "unlisted"


def test_analytics_returns_totals_and_rejects_unknown_dimension(client: TestClient) -> None:
    ok = client.get(
        "/api/v1/channels/youtube/analytics",
        params={"range": "7", "dimensions": "day"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["analytics"]["available"] is True
    assert body["analytics"]["totals"]["views"] == 1000.0
    assert body["source"] == "youtube_analytics_api"

    bad = client.get(
        "/api/v1/channels/youtube/analytics", params={"dimensions": "day,unknownDim"}
    )
    assert bad.status_code == 400


def test_analytics_scope_limitation_is_explained(
    client: TestClient, analytics_port: FakeAnalyticsPort
) -> None:
    analytics_port.available = False
    response = client.get("/api/v1/channels/youtube/analytics", params={"range": "28"})

    assert response.status_code == 200
    body = response.json()
    assert body["analytics"]["available"] is False
    assert body["source"] is None
    assert "yt-analytics.readonly" in body["explanation"]


def test_insufficient_scope_maps_to_403(client: TestClient) -> None:
    def raise_scope() -> None:
        raise InsufficientScopeException("scope:x", "Yorum yanıtlama")

    app.dependency_overrides[container.get_list_comments_use_case] = lambda: type(
        "UseCase", (), {"execute": staticmethod(lambda **kwargs: raise_scope())}
    )()

    response = client.get("/api/v1/comments")
    assert response.status_code == 403
    assert response.json()["required_scope"] == "scope:x"


def test_comments_list_reply_and_moderation(client: TestClient) -> None:
    listed = client.get("/api/v1/comments", params={"video_id": "v1"})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["comment_id"] == "c1"

    reply = client.post("/api/v1/comments/c1/reply", json={"text": "Teşekkürler"})
    assert reply.status_code == 200
    assert reply.json()["comment"]["text"] == "Teşekkürler"

    empty_reply = client.post("/api/v1/comments/c1/reply", json={"text": "   "})
    assert empty_reply.status_code == 400

    moderation = client.post(
        "/api/v1/comments/c1/moderation", json={"status": "heldForReview"}
    )
    assert moderation.status_code == 200
    assert moderation.json()["comment"]["moderation_status"] == "heldForReview"
