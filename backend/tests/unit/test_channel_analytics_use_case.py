"""Previous-period comparison behaviour of the analytics use case.

Every port is a local fake, so no request leaves the process.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from tezlify_studio.application.ports.creator_gateway_port import CreatorSession
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.application.use_cases.get_channel_analytics_use_case import (
    GetChannelAnalyticsUseCase,
)
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    AnalyticsRow,
    DateRange,
)
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    SCOPE_ANALYTICS,
    SCOPE_REVENUE,
)


class RecordingAnalyticsPort:
    def __init__(
        self,
        current_totals: Dict[str, float],
        previous_totals: Optional[Dict[str, float]] = None,
        previous_available: bool = True,
        previous_reason: Optional[str] = None,
        revenue: Optional[Dict[str, Any]] = None,
        current_rows: Optional[List[AnalyticsRow]] = None,
        previous_rows: Optional[List[AnalyticsRow]] = None,
    ) -> None:
        self.current_totals = current_totals
        self.previous_totals = previous_totals or {}
        self.previous_available = previous_available
        self.previous_reason = previous_reason
        self.revenue = revenue
        self.current_rows = current_rows or []
        self.previous_rows = previous_rows or []
        self.calls: List[Dict[str, Any]] = []

    def query(
        self,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        self.calls.append(
            {
                "start_date": date_range.start_date,
                "end_date": date_range.end_date,
                "days": date_range.days,
                "label": date_range.label,
                "dimensions": list(dimensions or []),
                "include_revenue": include_revenue,
            }
        )
        is_previous = date_range.label.startswith("previous_")
        if is_previous and not self.previous_available:
            return AnalyticsResult(
                available=False,
                reason=self.previous_reason,
                start_date=date_range.start_date.isoformat(),
                end_date=date_range.end_date.isoformat(),
            )
        return AnalyticsResult(
            available=True,
            start_date=date_range.start_date.isoformat(),
            end_date=date_range.end_date.isoformat(),
            metrics=list(metrics or []),
            dimensions=list(dimensions or []),
            totals=dict(self.previous_totals if is_previous else self.current_totals),
            rows=list(self.previous_rows if is_previous else self.current_rows),
            revenue=self.revenue,
        )


class FakeResolver:
    def __init__(self, scopes: Optional[List[str]] = None) -> None:
        self.scopes = scopes or [SCOPE_ANALYTICS, SCOPE_REVENUE]

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
                granted_scopes=list(self.scopes),
            ),
        )


class FakeGateway:
    def __init__(self, analytics: RecordingAnalyticsPort) -> None:
        self.analytics = analytics

    def bind(self, context: ChannelContext) -> CreatorSession:
        return CreatorSession(
            channel=None,  # type: ignore[arg-type]
            analytics=self.analytics,  # type: ignore[arg-type]
            comments=None,  # type: ignore[arg-type]
            access=ChannelAccess(
                platform=SocialPlatform.YOUTUBE,
                channel_id=context.channel_id,
                external_channel_id=context.external_channel_id,
                connection_id=context.connection_id,
                access_token="mock_access_token",
            ),
        )


def build_use_case(
    analytics: RecordingAnalyticsPort, scopes: Optional[List[str]] = None
) -> GetChannelAnalyticsUseCase:
    return GetChannelAnalyticsUseCase(
        FakeResolver(scopes),
        FakeGateway(analytics),
        capability_service=YouTubeCapabilityService(),
    )


def test_previous_range_covers_equal_length_window_before_current() -> None:
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 150.0},
        previous_totals={"views": 50.0},
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="custom",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 30),
        compare=True,
    )

    assert len(analytics.calls) == 2
    previous = analytics.calls[1]
    assert previous["start_date"] == date(2026, 9, 1)
    assert previous["end_date"] == date(2026, 9, 30)
    assert previous["days"] == 30
    comparison = response["comparison"]
    assert comparison["available"] is True
    assert comparison["range"] == {
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "days": 30,
    }
    assert comparison["totals"] == {"views": 50.0}


def test_deltas_report_change_and_percent_with_zero_baseline() -> None:
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 150.0, "estimatedMinutesWatched": 100.0},
        previous_totals={"views": 50.0, "estimatedMinutesWatched": 0.0},
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="custom",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 30),
        compare=True,
    )

    deltas = response["comparison"]["deltas"]
    assert deltas["views"] == {
        "current": 150.0,
        "previous": 50.0,
        "change": 100.0,
        "percent": 200.0,
    }
    assert deltas["estimatedMinutesWatched"]["change"] == 100.0
    assert deltas["estimatedMinutesWatched"]["percent"] is None


def test_compare_disabled_makes_a_single_analytics_call() -> None:
    analytics = RecordingAnalyticsPort(current_totals={"views": 10.0})
    use_case = build_use_case(analytics)

    response = use_case.execute(range_key="28")

    assert len(analytics.calls) == 1
    assert response["comparison"] is None


def test_unavailable_previous_period_is_reported_without_deltas() -> None:
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 150.0},
        previous_available=False,
        previous_reason="insufficient_scope",
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="custom",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 30),
        compare=True,
    )

    comparison = response["comparison"]
    assert comparison["available"] is False
    assert comparison["reason"] == "insufficient_scope"
    assert comparison["range"]["start_date"] == "2026-09-01"
    assert "deltas" not in comparison


def test_revenue_deltas_follow_the_same_previous_window() -> None:
    revenue = {
        "available": True,
        "currency": "USD",
        "amount": 12.0,
        "ad_revenue": 9.0,
    }
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 150.0},
        previous_totals={"views": 50.0},
        revenue=revenue,
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="custom",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 30),
        include_revenue=True,
        compare=True,
    )

    assert analytics.calls[1]["include_revenue"] is True
    revenue_delta = response["comparison"]["revenue"]
    assert revenue_delta["amount"]["change"] == 0.0
    assert revenue_delta["amount"]["percent"] == 0.0
    assert revenue_delta["ad_revenue"]["current"] == 9.0


def test_missing_analytics_scope_skips_the_comparison_call() -> None:
    analytics = RecordingAnalyticsPort(current_totals={"views": 10.0})
    use_case = build_use_case(analytics, scopes=[SCOPE_REVENUE])

    response = use_case.execute(range_key="28", compare=True)

    assert analytics.calls == []
    assert response["analytics"].available is False
    assert response["analytics"].reason == "insufficient_scope"
    assert response["comparison"] is None


def test_row_comparison_matches_dimension_values_across_periods() -> None:
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 180.0},
        previous_totals={"views": 60.0},
        current_rows=[
            AnalyticsRow(dimensions={"video": "vid_a"}, metrics={"views": 150.0}),
            AnalyticsRow(dimensions={"video": "vid_new"}, metrics={"views": 30.0}),
        ],
        previous_rows=[
            AnalyticsRow(dimensions={"video": "vid_a"}, metrics={"views": 50.0}),
            AnalyticsRow(dimensions={"video": "vid_old"}, metrics={"views": 10.0}),
        ],
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="custom",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 30),
        dimensions=["video"],
        compare=True,
    )

    rows = response["comparison"]["rows"]
    assert [row["dimensions"]["video"] for row in rows] == ["vid_a", "vid_new"]

    matched = rows[0]
    assert matched["previous_metrics"] == {"views": 50.0}
    assert matched["deltas"]["views"] == {
        "current": 150.0,
        "previous": 50.0,
        "change": 100.0,
        "percent": 200.0,
    }

    new_video = rows[1]
    assert new_video["previous_metrics"] == {}
    assert new_video["deltas"] == {}


def test_rows_stay_visible_when_previous_window_has_no_rows() -> None:
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 1.0},
        previous_totals={"views": 0.0},
        current_rows=[
            AnalyticsRow(dimensions={"video": "vid_a"}, metrics={"views": 1.0})
        ],
        previous_rows=[],
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="28", dimensions=["video"], compare=True
    )

    rows = response["comparison"]["rows"]
    assert len(rows) == 1
    assert rows[0]["dimensions"] == {"video": "vid_a"}
    assert rows[0]["previous_metrics"] == {}
    assert rows[0]["deltas"] == {}


def test_day_dimension_rows_are_not_compared_because_dates_differ() -> None:
    analytics = RecordingAnalyticsPort(
        current_totals={"views": 10.0},
        previous_totals={"views": 8.0},
        current_rows=[
            AnalyticsRow(dimensions={"day": "2026-10-01"}, metrics={"views": 10.0})
        ],
        previous_rows=[
            AnalyticsRow(dimensions={"day": "2026-09-01"}, metrics={"views": 8.0})
        ],
    )
    use_case = build_use_case(analytics)

    response = use_case.execute(
        range_key="custom",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 30),
        dimensions=["day"],
        compare=True,
    )

    assert response["comparison"]["rows"] == []
    assert response["comparison"]["deltas"]["views"]["percent"] == 25.0
