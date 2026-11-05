"""Dashboard aggregation must label sources and never fabricate values."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from tezlify_studio.application.ports.creator_gateway_port import CreatorSession
from tezlify_studio.application.use_cases.get_dashboard_use_case import GetDashboardUseCase
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import (
    PrivacyStatus,
    PublishStatus,
    SocialPlatform,
)
from tezlify_studio.domain.exceptions.creator_exceptions import ChannelNotFoundException
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    ChannelProfile,
    ChannelVideo,
    DateRange,
)


def channel_context() -> ChannelContext:
    return ChannelContext(
        channel=PlatformChannel(
            id="ch_1",
            platform_connection_id="conn_1",
            platform=SocialPlatform.YOUTUBE,
            channel_external_id="UC_X",
            channel_name="Kanal",
        ),
        connection=PlatformConnection(
            id="conn_1",
            platform=SocialPlatform.YOUTUBE,
            account_external_id="google_1",
            account_display_name="Hesap",
        ),
    )


class Resolver:
    def __init__(self, context: Optional[ChannelContext]) -> None:
        self.context = context

    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        if self.context is None:
            raise ChannelNotFoundException(channel_id or "none")
        return self.context


class ChannelPort:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def get_channel(self) -> ChannelProfile:
        if self.fail:
            raise RuntimeError("data api down")
        return ChannelProfile(channel_id="UC_X", title="Kanal", subscriber_count=10)

    def list_videos(self, max_results: int = 25, page_token: Optional[str] = None) -> Dict[str, Any]:
        return {"items": [ChannelVideo(video_id="v1", title="Video")]}


class AnalyticsPortStub:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def query(
        self,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        if self.fail:
            raise RuntimeError("analytics down")
        return AnalyticsResult(
            available=True,
            totals={"views": 5.0},
            rows=[],
            start_date=date_range.start_date.isoformat(),
            end_date=date_range.end_date.isoformat(),
        )


class CommentsPort:
    def list_comments(self, *args: Any, **kwargs: Any) -> List[Any]:
        return []


class Gateway:
    def __init__(self, channel_fail: bool = False, analytics_fail: bool = False) -> None:
        self.channel_fail = channel_fail
        self.analytics_fail = analytics_fail

    def list_platforms(self) -> List[Any]:
        return []

    def bind(self, context: ChannelContext) -> CreatorSession:
        return CreatorSession(
            channel=ChannelPort(fail=self.channel_fail),
            analytics=AnalyticsPortStub(fail=self.analytics_fail),
            comments=CommentsPort(),
            access=ChannelAccess(
                platform=SocialPlatform.YOUTUBE,
                channel_id=context.channel_id,
                external_channel_id=context.external_channel_id,
                connection_id=context.connection_id,
                access_token="mock_token",
            ),
        )


class PublishRepo:
    def __init__(self, records: Optional[List[PublishRecord]] = None) -> None:
        self.records = records or []

    def list_by_platform(
        self,
        platform: SocialPlatform,
        limit: int = 500,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> List[PublishRecord]:
        return [item for item in self.records if channel_id is None or item.channel_id == channel_id]


class ScheduleRepo:
    def list_upcoming(
        self, now: datetime, limit: int = 5, channel_id: Optional[str] = None
    ) -> List[Any]:
        return []


def build_use_case(
    *,
    connected: bool,
    channel_fail: bool = False,
    analytics_fail: bool = False,
    records: Optional[List[PublishRecord]] = None,
) -> GetDashboardUseCase:
    return GetDashboardUseCase(
        resolver=Resolver(channel_context() if connected else None),
        gateway=Gateway(channel_fail=channel_fail, analytics_fail=analytics_fail),
        publish_repo=PublishRepo(records),
        schedule_repo=ScheduleRepo(),
    )


def test_disconnected_dashboard_returns_local_data_and_no_channel_claims() -> None:
    snapshot = build_use_case(connected=False).execute(range_key="28")

    assert snapshot.connected is False
    assert snapshot.channel is None
    assert snapshot.analytics is None
    assert snapshot.range_days == 28
    assert snapshot.warnings
    assert snapshot.sources["views_over_time"] == "youtube_analytics_api"
    assert snapshot.sources["scheduled_uploads"] == "local_database"
    assert snapshot.local_counts["scope"] == "none"


def test_connected_dashboard_pulls_real_channel_and_analytics() -> None:
    snapshot = build_use_case(connected=True).execute(range_key="7")

    assert snapshot.connected is True
    assert snapshot.channel is not None
    assert snapshot.channel.title == "Kanal"
    assert snapshot.recent_videos[0].video_id == "v1"
    assert snapshot.analytics is not None
    assert snapshot.analytics.totals == {"views": 5.0}
    assert snapshot.warnings == []
    assert snapshot.channel_context["channel_id"] == "ch_1"
    assert snapshot.local_counts["scope"] == "channel"


def test_api_failures_degrade_to_warnings_without_values() -> None:
    snapshot = build_use_case(
        connected=True, channel_fail=True, analytics_fail=True
    ).execute()

    assert snapshot.channel is None
    assert snapshot.analytics is None
    assert snapshot.recent_videos == []
    assert any("Data API" in warning for warning in snapshot.warnings)
    assert any("Analytics" in warning for warning in snapshot.warnings)


def test_publish_counts_are_computed_from_local_records() -> None:
    now = datetime.now(timezone.utc)
    records = [
        PublishRecord(
            id="p1",
            media_asset_id="m1",
            platform=SocialPlatform.YOUTUBE,
            title="Yayınlandı",
            privacy_status=PrivacyStatus.PUBLIC,
            status=PublishStatus.PUBLISHED,
            created_at=now,
            published_at=now,
            channel_id="ch_1",
        ),
        PublishRecord(
            id="p2",
            media_asset_id="m2",
            platform=SocialPlatform.YOUTUBE,
            title="Hatalı",
            privacy_status=PrivacyStatus.PRIVATE,
            status=PublishStatus.FAILED,
            created_at=now - timedelta(days=1),
            channel_id="ch_1",
        ),
    ]

    snapshot = build_use_case(connected=True, records=records).execute()

    assert snapshot.local_counts["total_publish_records"] == 2
    assert snapshot.local_counts["publish_status_counts"]["published"] == 1
    assert snapshot.local_counts["publish_status_counts"]["failed"] == 1
    assert snapshot.recent_publishes[0]["id"] == "p1"
