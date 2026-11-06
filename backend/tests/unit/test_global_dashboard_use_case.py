"""Global dashboard counts must only include usable (enabled) channels."""

from __future__ import annotations

from typing import Any, List

from tezlify_studio.application.use_cases.get_global_dashboard_use_case import (
    GetGlobalDashboardUseCase,
)
from tezlify_studio.domain.entities.channel_selection import ChannelSelection
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.publish_status import SocialPlatform


def make_channel(
    channel_id: str,
    name: str,
    *,
    is_primary: bool = False,
    is_enabled: bool = True,
) -> PlatformChannel:
    return PlatformChannel(
        id=channel_id,
        platform_connection_id="conn_1",
        platform=SocialPlatform.YOUTUBE,
        channel_external_id=f"UC_{channel_id}",
        channel_name=name,
        is_primary=is_primary,
        is_enabled=is_enabled,
    )


class ConnectionRepo:
    def __init__(self, connections: List[PlatformConnection]) -> None:
        self.connections = connections

    def list_all(self, include_disconnected: bool = False) -> List[PlatformConnection]:
        return self.connections


class ChannelRepo:
    def __init__(self, channels: List[PlatformChannel]) -> None:
        self.channels = channels

    def list_by_connection(self, connection_id: str) -> List[PlatformChannel]:
        return [item for item in self.channels if item.platform_connection_id == connection_id]


class SelectionRepo:
    def get(self) -> ChannelSelection:
        return ChannelSelection(active_channel_id="ch_enabled", default_platform="youtube")


class PublishRepo:
    def list_by_platform(self, *args: Any, **kwargs: Any) -> List[Any]:
        return []


class ScheduleRepo:
    def list_all(self, *args: Any, **kwargs: Any) -> List[Any]:
        return []


def build_use_case(channels: List[PlatformChannel]) -> GetGlobalDashboardUseCase:
    connection = PlatformConnection(
        id="conn_1",
        platform=SocialPlatform.YOUTUBE,
        account_external_id="google:sub-1",
        account_display_name="Test Hesap",
        granted_scopes=[],
    )
    return GetGlobalDashboardUseCase(
        connection_repo=ConnectionRepo([connection]),
        channel_repo=ChannelRepo(channels),
        selection_repo=SelectionRepo(),
        publish_repo=PublishRepo(),
        schedule_repo=ScheduleRepo(),
    )


def test_dashboard_counts_only_enabled_channels() -> None:
    snapshot = build_use_case(
        [
            make_channel("ch_enabled", "Gerçek Kanal", is_primary=True),
            make_channel(
                "ch_legacy",
                "UC_RESILIENCE",
                is_primary=True,
                is_enabled=False,
            ),
        ]
    ).execute()

    assert snapshot["totals"]["channels"] == 1
    assert snapshot["platforms"][0]["channels"] == 1
    account = snapshot["accounts"][0]
    assert account["channel_count"] == 1
    assert [item.id for item in account["channels"]] == ["ch_enabled"]


def test_dashboard_without_enabled_channels_reports_zero() -> None:
    snapshot = build_use_case(
        [make_channel("ch_legacy", "UC_RESILIENCE", is_primary=True, is_enabled=False)]
    ).execute()

    assert snapshot["totals"]["channels"] == 0
    assert snapshot["platforms"][0]["channels"] == 0
    account = snapshot["accounts"][0]
    assert account["channel_count"] == 0
    assert account["channels"] == []
