from datetime import datetime, timezone
from typing import Any, Dict, Optional

from tezlify_studio.application.dto.connection_dto import (
    channel_context_payload,
    channel_to_dto,
)
from tezlify_studio.application.dto.creator_dto import DashboardSnapshot
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.services.analytics_range import resolve_date_range
from tezlify_studio.domain.enums.publish_status import PublishStatus, SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import CreatorStudioException
from tezlify_studio.domain.value_objects.creator_models import YOUTUBE_ANALYTICS_METRICS


class GetDashboardUseCase:
    """Channel dashboard built strictly from one validated channel context."""

    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        gateway: CreatorGatewayPort,
        publish_repo: PublishRecordRepositoryPort,
        schedule_repo: ScheduledPublishRepositoryPort,
        default_range_days: int = 28,
        max_range_days: int = 365,
    ):
        self.resolver = resolver
        self.gateway = gateway
        self.publish_repo = publish_repo
        self.schedule_repo = schedule_repo
        self.default_range_days = default_range_days
        self.max_range_days = max_range_days

    def execute(
        self, range_key: str = "28", channel_id: Optional[str] = None
    ) -> DashboardSnapshot:
        date_range = resolve_date_range(
            range_key=range_key or str(self.default_range_days),
            max_days=self.max_range_days,
        )
        snapshot = DashboardSnapshot(
            connected=False,
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

        try:
            context = self.resolver.resolve(channel_id)
        except CreatorStudioException as exc:
            snapshot.warnings.append(str(exc))
            snapshot.warnings.append(
                "Bağlı YouTube kanalı yok. Kanalı bağlayınca gerçek veriler burada görünür."
            )
            self._fill_local(snapshot, None)
            return snapshot

        snapshot.connected = True
        snapshot.channel_context = channel_context_payload(context)
        snapshot.local_counts["channel"] = channel_to_dto(context.channel).__dict__
        self._fill_local(snapshot, context.channel_id)

        session = self.gateway.bind(context)
        try:
            snapshot.channel = session.channel.get_channel()
            videos = session.channel.list_videos(max_results=5)
            snapshot.recent_videos = videos.get("items", [])
        except Exception as exc:  # noqa: BLE001 - dashboard must degrade, not fail
            snapshot.warnings.append(f"YouTube Data API verisi alınamadı: {exc}")

        try:
            snapshot.analytics = session.analytics.query(
                date_range=date_range,
                metrics=list(YOUTUBE_ANALYTICS_METRICS),
                dimensions=["day"],
            )
        except Exception as exc:  # noqa: BLE001
            snapshot.warnings.append(f"YouTube Analytics verisi alınamadı: {exc}")

        return snapshot

    def _fill_local(
        self, snapshot: DashboardSnapshot, channel_id: Optional[str]
    ) -> None:
        records = []
        if channel_id:
            try:
                records = self.publish_repo.list_by_platform(
                    SocialPlatform.YOUTUBE,
                    limit=500,
                    offset=0,
                    channel_id=channel_id,
                )
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
                "scope": "channel" if channel_id else "none",
            }
        )
        snapshot.recent_publishes = [
            {
                "id": record.id,
                "title": record.title,
                "status": record.status.value,
                "privacy_status": record.privacy_status.value,
                "external_video_id": record.external_video_id,
                "channel_id": record.channel_id,
                "published_at": record.published_at.isoformat() if record.published_at else None,
                "created_at": record.created_at.isoformat(),
            }
            for record in sorted(records, key=lambda item: item.created_at, reverse=True)[:5]
        ]

        upcoming = []
        if channel_id:
            try:
                upcoming = self.schedule_repo.list_upcoming(
                    datetime.now(timezone.utc), limit=5, channel_id=channel_id
                )
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
                "channel_id": item.channel_id,
            }
            for item in upcoming
        ]
        snapshot.local_counts["upcoming_schedule_count"] = len(upcoming)
