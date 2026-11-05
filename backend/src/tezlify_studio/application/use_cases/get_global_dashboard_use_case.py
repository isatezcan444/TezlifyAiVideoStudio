from datetime import datetime, timezone
from typing import Any, Dict, List

from tezlify_studio.application.dto.connection_dto import connection_to_dto
from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.domain.enums.publish_status import PublishStatus, SocialPlatform


class GetGlobalDashboardUseCase:
    """Workspace-wide overview.

    Only local record counts are aggregated here. YouTube metrics are never
    summed across channels because subscriber/view semantics differ per range
    and per channel; those live on the channel dashboard.
    """

    def __init__(
        self,
        connection_repo: PlatformConnectionRepositoryPort,
        channel_repo: PlatformChannelRepositoryPort,
        selection_repo: ChannelSelectionRepositoryPort,
        publish_repo: PublishRecordRepositoryPort,
        schedule_repo: ScheduledPublishRepositoryPort,
    ):
        self.connection_repo = connection_repo
        self.channel_repo = channel_repo
        self.selection_repo = selection_repo
        self.publish_repo = publish_repo
        self.schedule_repo = schedule_repo

    def execute(self) -> Dict[str, Any]:
        connections = self.connection_repo.list_all(include_disconnected=True)
        channel_counts: Dict[str, int] = {}
        for connection in connections:
            channel_counts[connection.id] = len(
                self.channel_repo.list_by_connection(connection.id)
            )

        accounts = [
            connection_to_dto(
                connection, self.channel_repo.list_by_connection(connection.id)
            ).__dict__
            for connection in connections
        ]

        records = self.publish_repo.list_by_platform(
            SocialPlatform.YOUTUBE, limit=100000, offset=0
        )
        status_counts: Dict[str, int] = {}
        for record in records:
            key = record.status.value if hasattr(record.status, "value") else str(record.status)
            status_counts[key] = status_counts.get(key, 0) + 1

        schedules = self.schedule_repo.list_all(limit=100000)
        schedule_counts: Dict[str, int] = {}
        for item in schedules:
            key = item.status.value if hasattr(item.status, "value") else str(item.status)
            schedule_counts[key] = schedule_counts.get(key, 0) + 1

        selection = self.selection_repo.get()
        platform_overview: List[Dict[str, Any]] = []
        youtube_connections = [
            connection for connection in connections if connection.platform == SocialPlatform.YOUTUBE
        ]
        if youtube_connections:
            platform_overview.append(
                {
                    "platform": "youtube",
                    "display_name": "YouTube",
                    "implemented": True,
                    "accounts": len(youtube_connections),
                    "active_accounts": sum(
                        1 for connection in youtube_connections if connection.is_active
                    ),
                    "channels": sum(
                        channel_counts.get(connection.id, 0)
                        for connection in youtube_connections
                    ),
                    "publish_records": len(records),
                    "scheduled_records": len(schedules),
                }
            )

        return {
            "connected": bool(youtube_connections),
            "platforms": platform_overview,
            "accounts": accounts,
            "selection": {
                "active_channel_id": selection.active_channel_id,
                "default_platform": selection.default_platform,
            },
            "totals": {
                "accounts": len(connections),
                "channels": sum(channel_counts.values()),
                "publish_records": len(records),
                "scheduled_records": len(schedules),
                "publish_status_counts": status_counts,
                "schedule_status_counts": schedule_counts,
            },
            "sources": {
                "accounts": "local_database",
                "channels": "local_database",
                "publish_records": "local_database",
                "scheduled_records": "local_database",
            },
            "notes": [
                "Bu ekran yalnızca yerel kayıtları toplar; YouTube metrikleri kanal bazında ayrı gösterilir.",
                "Abone, görüntüleme ve izlenme süresi farklı kanallar arasında toplanmaz.",
                f"Son güncelleme: {datetime.now(timezone.utc).isoformat()}",
            ],
            "unresolved_publish_records": sum(
                1
                for record in records
                if getattr(record, "channel_attribution", "") == "unresolved"
            ),
        }
