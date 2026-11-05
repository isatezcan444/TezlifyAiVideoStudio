import os
import sys

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from tezlify_studio.application.services.channel_context_service import ChannelContextService
from tezlify_studio.application.services.connection_token_provider import ConnectionTokenProvider
from tezlify_studio.application.use_cases.cancel_scheduled_publish_use_case import (
    CancelScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.cancel_youtube_upload_use_case import (
    CancelYouTubeUploadUseCase,
)
from tezlify_studio.application.use_cases.channel_selection_use_case import (
    ChannelSelectionUseCase,
)
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import (
    CompleteYouTubeAuthenticationUseCase,
)
from tezlify_studio.application.use_cases.create_scheduled_publish_use_case import (
    CreateScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.delete_media_use_case import DeleteMediaUseCase
from tezlify_studio.application.use_cases.disconnect_platform_connection_use_case import (
    DisconnectPlatformConnectionUseCase,
)
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import (
    GenerateYouTubeAuthUrlUseCase,
)
from tezlify_studio.application.use_cases.get_channel_analytics_use_case import (
    GetChannelAnalyticsUseCase,
)
from tezlify_studio.application.use_cases.get_channel_overview_use_case import (
    GetChannelOverviewUseCase,
)
from tezlify_studio.application.use_cases.get_channel_video_use_case import (
    GetChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.get_dashboard_use_case import GetDashboardUseCase
from tezlify_studio.application.use_cases.get_global_dashboard_use_case import (
    GetGlobalDashboardUseCase,
)
from tezlify_studio.application.use_cases.get_media_use_case import GetMediaUseCase
from tezlify_studio.application.use_cases.get_scheduled_publish_use_case import (
    GetScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.get_system_status_use_case import (
    GetSystemStatusUseCase,
)
from tezlify_studio.application.use_cases.get_upcoming_publishes_use_case import (
    GetUpcomingPublishesUseCase,
)
from tezlify_studio.application.use_cases.get_youtube_publish_status_use_case import (
    GetYouTubePublishStatusUseCase,
)
from tezlify_studio.application.use_cases.import_video_use_case import ImportVideoUseCase
from tezlify_studio.application.use_cases.list_channel_playlists_use_case import (
    ListChannelPlaylistsUseCase,
)
from tezlify_studio.application.use_cases.list_channel_videos_use_case import (
    ListChannelVideosUseCase,
)
from tezlify_studio.application.use_cases.list_comments_use_case import ListCommentsUseCase
from tezlify_studio.application.use_cases.list_media_use_case import ListMediaUseCase
from tezlify_studio.application.use_cases.list_platform_connections_use_case import (
    ListPlatformConnectionsUseCase,
)
from tezlify_studio.application.use_cases.list_platforms_use_case import ListPlatformsUseCase
from tezlify_studio.application.use_cases.list_publish_records_use_case import (
    ListPublishRecordsUseCase,
)
from tezlify_studio.application.use_cases.list_scheduled_publishes_use_case import (
    ListScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.list_video_categories_use_case import (
    ListVideoCategoriesUseCase,
)
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.application.use_cases.reply_to_comment_use_case import (
    ReplyToCommentUseCase,
)
from tezlify_studio.application.use_cases.resume_youtube_upload_use_case import (
    ResumeYouTubeUploadUseCase,
)
from tezlify_studio.application.use_cases.retry_failed_scheduled_publish_use_case import (
    RetryFailedScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.set_comment_moderation_use_case import (
    SetCommentModerationUseCase,
)
from tezlify_studio.application.use_cases.update_channel_video_use_case import (
    UpdateChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.update_scheduled_publish_use_case import (
    UpdateScheduledPublishUseCase,
)
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.media.local_media_storage import LocalMediaStorage
from tezlify_studio.infrastructure.media.video_probe_impl import VideoProbeImpl
from tezlify_studio.infrastructure.media.youtube_api_client_impl import YouTubeApiClientImpl
from tezlify_studio.infrastructure.persistence.database import SessionLocal, get_db
from tezlify_studio.infrastructure.persistence.repositories.channel_selection_repository_impl import (
    ChannelSelectionRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import (
    MediaRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.platform_channel_repository_impl import (
    PlatformChannelRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.platform_connection_repository_impl import (
    PlatformConnectionRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import (
    PublishRecordRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
    ScheduledPublishRepositoryImpl,
)
from tezlify_studio.infrastructure.scheduler.scheduler_service import (
    PublishSchedulerService,
)
from tezlify_studio.infrastructure.security.token_storage_impl import (
    InMemoryTokenStorageAdapter,
    KeychainTokenStorageAdapter,
)
from tezlify_studio.infrastructure.youtube.youtube_creator_gateway import (
    YouTubeCreatorGateway,
)

# Singleton instances
media_storage = LocalMediaStorage(settings.media_dir, settings.temp_dir)
video_probe = VideoProbeImpl()

# Strict Environment Isolation: InMemoryTokenStorageAdapter is strictly reserved for pytest / CI
_is_test_runner = os.environ.get("TEZLIFY_TEST_ENV") == "1" or "pytest" in sys.modules
token_storage = (
    InMemoryTokenStorageAdapter()
    if _is_test_runner
    else KeychainTokenStorageAdapter(fallback_to_memory=False)
)
youtube_publisher = YouTubeApiClientImpl()
_creator_http_client = httpx.Client(timeout=30.0)


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------
def get_repository(db: Session = Depends(get_db)) -> MediaRepositoryImpl:
    return MediaRepositoryImpl(db)


def get_publish_record_repository(
    db: Session = Depends(get_db),
) -> PublishRecordRepositoryImpl:
    return PublishRecordRepositoryImpl(db)


def get_scheduled_publish_repository(
    db: Session = Depends(get_db),
) -> ScheduledPublishRepositoryImpl:
    return ScheduledPublishRepositoryImpl(db)


def get_platform_connection_repository(
    db: Session = Depends(get_db),
) -> PlatformConnectionRepositoryImpl:
    return PlatformConnectionRepositoryImpl(db)


def get_platform_channel_repository(
    db: Session = Depends(get_db),
) -> PlatformChannelRepositoryImpl:
    return PlatformChannelRepositoryImpl(db)


def get_channel_selection_repository(
    db: Session = Depends(get_db),
) -> ChannelSelectionRepositoryImpl:
    return ChannelSelectionRepositoryImpl(db)


def get_storage() -> LocalMediaStorage:
    return media_storage


def get_probe() -> VideoProbeImpl:
    return video_probe


def get_token_storage():
    return token_storage


def get_youtube_publisher() -> YouTubeApiClientImpl:
    return youtube_publisher


# ---------------------------------------------------------------------------
# Channel context services
# ---------------------------------------------------------------------------
def get_channel_context_service(
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
    channel_repo: PlatformChannelRepositoryImpl = Depends(
        get_platform_channel_repository
    ),
    selection_repo: ChannelSelectionRepositoryImpl = Depends(
        get_channel_selection_repository
    ),
) -> ChannelContextService:
    return ChannelContextService(connection_repo, channel_repo, selection_repo)


def get_access_provider(
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
    storage=Depends(get_token_storage),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> ConnectionTokenProvider:
    return ConnectionTokenProvider(connection_repo, storage, publisher)


def get_creator_gateway(
    access_provider: ConnectionTokenProvider = Depends(get_access_provider),
) -> YouTubeCreatorGateway:
    return YouTubeCreatorGateway(access_provider, client=_creator_http_client)


# ---------------------------------------------------------------------------
# Media use cases
# ---------------------------------------------------------------------------
def get_import_use_case(
    repo: MediaRepositoryImpl = Depends(get_repository),
    storage: LocalMediaStorage = Depends(get_storage),
    probe: VideoProbeImpl = Depends(get_probe),
) -> ImportVideoUseCase:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    return ImportVideoUseCase(repo, storage, probe, max_upload_bytes=max_bytes)


def get_media_use_case(repo: MediaRepositoryImpl = Depends(get_repository)) -> GetMediaUseCase:
    return GetMediaUseCase(repo)


def get_list_use_case(repo: MediaRepositoryImpl = Depends(get_repository)) -> ListMediaUseCase:
    return ListMediaUseCase(repo)


def get_delete_use_case(
    repo: MediaRepositoryImpl = Depends(get_repository),
    storage: LocalMediaStorage = Depends(get_storage),
) -> DeleteMediaUseCase:
    return DeleteMediaUseCase(repo, storage)


def get_system_status_use_case(
    repo: MediaRepositoryImpl = Depends(get_repository),
    probe: VideoProbeImpl = Depends(get_probe),
) -> GetSystemStatusUseCase:
    return GetSystemStatusUseCase(repo, probe, settings.data_dir)


# ---------------------------------------------------------------------------
# OAuth / account management
# ---------------------------------------------------------------------------
def get_generate_youtube_auth_url_use_case(
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
) -> GenerateYouTubeAuthUrlUseCase:
    return GenerateYouTubeAuthUrlUseCase(publisher, connection_repo)


def get_complete_youtube_auth_use_case(
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
    channel_repo: PlatformChannelRepositoryImpl = Depends(
        get_platform_channel_repository
    ),
    selection_repo: ChannelSelectionRepositoryImpl = Depends(
        get_channel_selection_repository
    ),
    storage=Depends(get_token_storage),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> CompleteYouTubeAuthenticationUseCase:
    return CompleteYouTubeAuthenticationUseCase(
        connection_repo, channel_repo, selection_repo, storage, publisher
    )


def get_list_platform_connections_use_case(
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
    channel_repo: PlatformChannelRepositoryImpl = Depends(
        get_platform_channel_repository
    ),
) -> ListPlatformConnectionsUseCase:
    return ListPlatformConnectionsUseCase(connection_repo, channel_repo)


def get_disconnect_platform_connection_use_case(
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
    channel_repo: PlatformChannelRepositoryImpl = Depends(
        get_platform_channel_repository
    ),
    selection_repo: ChannelSelectionRepositoryImpl = Depends(
        get_channel_selection_repository
    ),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    schedule_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
    storage=Depends(get_token_storage),
) -> DisconnectPlatformConnectionUseCase:
    return DisconnectPlatformConnectionUseCase(
        connection_repo,
        channel_repo,
        selection_repo,
        publish_repo,
        schedule_repo,
        storage,
    )


def get_channel_selection_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    channel_repo: PlatformChannelRepositoryImpl = Depends(
        get_platform_channel_repository
    ),
) -> ChannelSelectionUseCase:
    return ChannelSelectionUseCase(resolver, channel_repo)


# ---------------------------------------------------------------------------
# Publish use cases
# ---------------------------------------------------------------------------
def _make_publish_repo_factory():
    def factory():
        db = SessionLocal()
        return PublishRecordRepositoryImpl(db), lambda: db.close()

    return factory


def get_publish_video_use_case(
    media_repo: MediaRepositoryImpl = Depends(get_repository),
    storage: LocalMediaStorage = Depends(get_storage),
    resolver: ChannelContextService = Depends(get_channel_context_service),
    access_provider: ConnectionTokenProvider = Depends(get_access_provider),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> PublishVideoToYouTubeUseCase:
    return PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=storage,
        resolver=resolver,
        access_provider=access_provider,
        publish_repo=publish_repo,
        publisher=publisher,
        repo_factory=_make_publish_repo_factory(),
    )


def get_resume_upload_use_case(
    publish_use_case: PublishVideoToYouTubeUseCase = Depends(get_publish_video_use_case),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    media_repo: MediaRepositoryImpl = Depends(get_repository),
    resolver: ChannelContextService = Depends(get_channel_context_service),
    access_provider: ConnectionTokenProvider = Depends(get_access_provider),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> ResumeYouTubeUploadUseCase:
    return ResumeYouTubeUploadUseCase(
        publish_use_case=publish_use_case,
        publish_repo=publish_repo,
        media_repo=media_repo,
        resolver=resolver,
        access_provider=access_provider,
        publisher=publisher,
    )


def get_cancel_upload_use_case(
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
) -> CancelYouTubeUploadUseCase:
    return CancelYouTubeUploadUseCase(publish_repo)


def get_publish_status_use_case(
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
) -> GetYouTubePublishStatusUseCase:
    return GetYouTubePublishStatusUseCase(publish_repo)


def get_list_publish_records_use_case(
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
) -> ListPublishRecordsUseCase:
    return ListPublishRecordsUseCase(publish_repo)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
publish_scheduler_service = PublishSchedulerService(
    storage=media_storage,
    token_storage=token_storage,
    youtube_publisher=youtube_publisher,
    check_interval_seconds=settings.scheduler_interval_seconds,
    grace_period_minutes=settings.scheduler_missed_grace_period_minutes,
    retry_delay_minutes=settings.scheduler_retry_delay_minutes,
)


def get_scheduler_service() -> PublishSchedulerService:
    return publish_scheduler_service


def get_create_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
    media_repo: MediaRepositoryImpl = Depends(get_repository),
    resolver: ChannelContextService = Depends(get_channel_context_service),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
) -> CreateScheduledPublishUseCase:
    return CreateScheduledPublishUseCase(sched_repo, media_repo, resolver, publish_repo)


def get_update_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> UpdateScheduledPublishUseCase:
    return UpdateScheduledPublishUseCase(sched_repo)


def get_cancel_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> CancelScheduledPublishUseCase:
    return CancelScheduledPublishUseCase(sched_repo)


def get_get_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> GetScheduledPublishUseCase:
    return GetScheduledPublishUseCase(sched_repo)


def get_list_scheduled_publishes_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> ListScheduledPublishesUseCase:
    return ListScheduledPublishesUseCase(sched_repo)


def get_upcoming_publishes_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> GetUpcomingPublishesUseCase:
    return GetUpcomingPublishesUseCase(sched_repo)


def get_retry_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> RetryFailedScheduledPublishUseCase:
    return RetryFailedScheduledPublishUseCase(sched_repo)


# ---------------------------------------------------------------------------
# Creator Studio: channel-scoped read/write use cases
# ---------------------------------------------------------------------------
def get_list_platforms_use_case(
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> ListPlatformsUseCase:
    return ListPlatformsUseCase(gateway)


def get_channel_overview_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> GetChannelOverviewUseCase:
    return GetChannelOverviewUseCase(resolver, gateway)


def get_list_channel_videos_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> ListChannelVideosUseCase:
    return ListChannelVideosUseCase(resolver, gateway)


def get_channel_video_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> GetChannelVideoUseCase:
    return GetChannelVideoUseCase(resolver, gateway)


def get_update_channel_video_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> UpdateChannelVideoUseCase:
    return UpdateChannelVideoUseCase(resolver, gateway)


def get_list_channel_playlists_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> ListChannelPlaylistsUseCase:
    return ListChannelPlaylistsUseCase(resolver, gateway)


def get_list_video_categories_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> ListVideoCategoriesUseCase:
    return ListVideoCategoriesUseCase(resolver, gateway)


def get_channel_analytics_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> GetChannelAnalyticsUseCase:
    return GetChannelAnalyticsUseCase(
        resolver, gateway, max_range_days=settings.analytics_max_range_days
    )


def get_list_comments_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> ListCommentsUseCase:
    return ListCommentsUseCase(resolver, gateway)


def get_reply_to_comment_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> ReplyToCommentUseCase:
    return ReplyToCommentUseCase(resolver, gateway)


def get_set_comment_moderation_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
) -> SetCommentModerationUseCase:
    return SetCommentModerationUseCase(resolver, gateway)


def get_dashboard_use_case(
    resolver: ChannelContextService = Depends(get_channel_context_service),
    gateway: YouTubeCreatorGateway = Depends(get_creator_gateway),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    schedule_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> GetDashboardUseCase:
    return GetDashboardUseCase(
        resolver=resolver,
        gateway=gateway,
        publish_repo=publish_repo,
        schedule_repo=schedule_repo,
        default_range_days=settings.analytics_default_range_days,
        max_range_days=settings.analytics_max_range_days,
    )


def get_global_dashboard_use_case(
    connection_repo: PlatformConnectionRepositoryImpl = Depends(
        get_platform_connection_repository
    ),
    channel_repo: PlatformChannelRepositoryImpl = Depends(
        get_platform_channel_repository
    ),
    selection_repo: ChannelSelectionRepositoryImpl = Depends(
        get_channel_selection_repository
    ),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    schedule_repo: ScheduledPublishRepositoryImpl = Depends(
        get_scheduled_publish_repository
    ),
) -> GetGlobalDashboardUseCase:
    return GetGlobalDashboardUseCase(
        connection_repo, channel_repo, selection_repo, publish_repo, schedule_repo
    )
