from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tezlify_studio.application.dto.creator_dto import DashboardSnapshot
from tezlify_studio.application.ports.analytics_port import AnalyticsPort
from tezlify_studio.application.ports.channel_port import ChannelPort
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.ports.social_account_repository_port import (
    SocialAccountRepositoryPort,
)
from tezlify_studio.application.services.analytics_range import resolve_date_range
from tezlify_studio.domain.enums.publish_status import PublishStatus, SocialPlatform
from tezlify_studio.domain.value_objects.creator_models import YOUTUBE_ANALYTICS_METRICS


class GetDashboardUseCase:
    def __init__(
        self,
        account_repo: SocialAccountRepositoryPort,
        channel_port: ChannelPort,
        analytics_port: AnalyticsPort,
        publish_repo: PublishRecordRepositoryPort,
        schedule_repo: ScheduledPublishRepositoryPort,
        default_range_days: int = 28,
        max_range_days: int = 365,
    ):
        self.account_repo = account_repo
        self.channel_port = channel_port
        self.analytics_port = analytics_port
        self.publish_repo = publish_repo
        self.schedule_repo = schedule_repo
        self.default_range_days = default_range_days
        self.max_range_days = max_range_days

    def execute(self, range_key: str = "28") -> DashboardSnapshot:
        date_range = resolve_date_range(
            range_key=range_key or str(self.default_range_days),
            max_days=self.max_range_days,
        )
        account = self.account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)

        snapshot = DashboardSnapshot(
            connected=account is not None,
            range_days=date_range.days,
            sources={
                "subscribers": "youtube_data_api",
                "total_views": "youtube_data_api",
                "video_count": "youtube_data_api",
                "views_over_time": "youtube_analytics_api",
                "subscriber_growth": "youtube_analytics_api",
                "recent_uploads": "youtube_data_api",
                "scheduled_uploads": "local_database",
                "publish_history": "local_database",
                "channel_status": "local_database",
            },
        )

        self._fill_local(snapshot)

        if account is None:
            snapshot.warnings.append(
                "Bağlı YouTube kanalı yok. Kanalı bağlayınca gerçek veriler burada görünür."
            )
            return snapshot

        snapshot.local_counts["account"] = {
            "id": account.id,
            "account_name": account.account_name,
            "channel_id": account.channel_id,
            "channel_avatar_url": account.channel_avatar_url,
            "is_token_expired": account.is_token_expired(),
        }

        try:
            snapshot.channel = self.channel_port.get_channel()
            videos = self.channel_port.list_videos(max_results=5)
            snapshot.recent_videos = videos.get("items", [])
        except Exception as exc:  # noqa: BLE001 - dashboard must degrade, not fail
            snapshot.warnings.append(f"YouTube Data API verisi alınamadı: {exc}")

        try:
            snapshot.analytics = self.analytics_port.query(
                date_range=date_range,
                metrics=list(YOUTUBE_ANALYTICS_METRICS),
                dimensions=["day"],
            )
        except Exception as exc:  # noqa: BLE001
            snapshot.warnings.append(f"YouTube Analytics verisi alınamadı: {exc}")

        return snapshot

    def _fill_local(self, snapshot: DashboardSnapshot) -> None:
        try:
            records = self.publish_repo.list_by_platform(SocialPlatform.YOUTUBE, limit=500, offset=0)
        except Exception:  # noqa: BLE001
            records = []

        counts = {
            PublishStatus.PUBLISHED.value: 0,
            PublishStatus.UPLOADING.value: 0,
            PublishStatus.PROCESSING.value: 0,
            PublishStatus.PENDING.value: 0,
            PublishStatus.FAILED.value: 0,
        }
        for record in records:
            key = record.status.value if hasattr(record.status, "value") else str(record.status)
            counts[key] = counts.get(key, 0) + 1

        snapshot.local_counts.update(
            {
                "total_publish_records": len(records),
                "publish_status_counts": counts,
            }
        )
        snapshot.recent_publishes = [
            {
                "id": record.id,
                "title": record.title,
                "status": record.status.value,
                "privacy_status": record.privacy_status.value,
                "external_video_id": record.external_video_id,
                "published_at": record.published_at.isoformat() if record.published_at else None,
                "created_at": record.created_at.isoformat(),
            }
            for record in sorted(records, key=lambda item: item.created_at, reverse=True)[:5]
        ]

        try:
            upcoming = self.schedule_repo.list_upcoming(datetime.now(timezone.utc), limit=5)
        except Exception:  # noqa: BLE001
            upcoming = []
        snapshot.upcoming_schedules = [
            {
                "id": item.id,
                "title": item.title,
                "scheduled_at_utc": item.scheduled_at_utc.isoformat(),
                "timezone": item.timezone,
                "status": item.status.value,
                "privacy_status": item.privacy_status.value,
            }
            for item in upcoming
        ]
        snapshot.local_counts["upcoming_schedule_count"] = len(upcoming)
