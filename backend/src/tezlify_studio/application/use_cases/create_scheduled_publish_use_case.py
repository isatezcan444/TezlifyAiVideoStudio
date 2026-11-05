import uuid
import zoneinfo
from datetime import datetime, timezone, timedelta
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.domain.exceptions.media_exceptions import (
    EntityNotFoundException,
    InvalidMediaFileException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    DuplicatePublishException,
)
from tezlify_studio.domain.exceptions.schedule_exceptions import (
    DuplicateScheduleException,
)
from tezlify_studio.domain.services.schedule_timezone_validator import (
    validate_and_normalize_schedule_time,
)
from tezlify_studio.application.dto.schedule_dto import (
    CreateScheduledPublishDTO,
    ScheduledPublishDTO,
)
from tezlify_studio.application.dto.mappers import scheduled_publish_to_dto

class CreateScheduledPublishUseCase:
    def __init__(
        self,
        schedule_repo: ScheduledPublishRepositoryPort,
        media_repo: MediaRepositoryPort,
        resolver: ChannelContextResolverPort,
        publish_repo: PublishRecordRepositoryPort,
    ):
        self.schedule_repo = schedule_repo
        self.media_repo = media_repo
        self.resolver = resolver
        self.publish_repo = publish_repo

    def execute(self, dto: CreateScheduledPublishDTO) -> ScheduledPublishDTO:
        # 1. Validate Media
        media = self.media_repo.get_by_id(dto.media_asset_id)
        if not media:
            raise EntityNotFoundException("MediaAsset", dto.media_asset_id)
        if media.status != MediaStatus.READY:
            raise InvalidMediaFileException("Video henüz işlenmedi veya hazır durumda değil.")

        # 2. Resolve and validate the target channel server-side
        context = self.resolver.resolve(dto.channel_id)

        # 3. Validate & Normalize Timezone & DateTime (including DST edge cases)
        tz_name = (dto.timezone or "UTC").strip()
        sched_utc = validate_and_normalize_schedule_time(dto.scheduled_at_iso, tz_name)

        # 4. Check for active schedule conflict (idempotency)
        existing_schedule = self.schedule_repo.get_active_by_media(
            media.id, SocialPlatform.YOUTUBE, channel_id=context.channel_id
        )
        if existing_schedule:
            raise DuplicateScheduleException(media.id, "youtube", existing_schedule.id)

        # 6. Check for active live publish conflict
        active_publish = self.publish_repo.get_active_by_media(
            media.id, SocialPlatform.YOUTUBE, channel_id=context.channel_id
        )
        if active_publish and active_publish.status in (
            PublishStatus.PENDING,
            PublishStatus.AUTHENTICATING,
            PublishStatus.UPLOADING,
            PublishStatus.PROCESSING,
        ):
            raise DuplicatePublishException(media.id, "youtube", active_publish.id)

        # 7. Create ScheduledPublish Entity
        schedule = ScheduledPublish(
            id=str(uuid.uuid4()),
            media_asset_id=media.id,
            channel_id=context.channel_id,
            platform_connection_id=context.connection_id,
            channel_attribution="exact",
            platform=SocialPlatform.YOUTUBE,
            title=dto.title.strip() or media.original_filename,
            description=dto.description.strip(),
            tags=dto.tags or [],
            privacy_status=PrivacyStatus(dto.privacy_status),
            scheduled_at_utc=sched_utc,
            timezone=tz_name,
            status=ScheduleStatus.SCHEDULED,
            max_attempts=dto.max_attempts,
        )

        saved = self.schedule_repo.save(schedule)
        return scheduled_publish_to_dto(saved)
