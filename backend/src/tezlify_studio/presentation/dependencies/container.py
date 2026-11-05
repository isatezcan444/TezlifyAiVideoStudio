import os
import sys
import httpx
from fastapi import Depends
from sqlalchemy.orm import Session
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import get_db, SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import MediaRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.social_account_repository_impl import SocialAccountRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.publish_record_repository_impl import PublishRecordRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.scheduled_publish_repository_impl import (
    ScheduledPublishRepositoryImpl,
)
from tezlify_studio.infrastructure.media.local_media_storage import LocalMediaStorage
from tezlify_studio.infrastructure.media.video_probe_impl import VideoProbeImpl
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.infrastructure.security.token_storage_impl import (
    KeychainTokenStorageAdapter,
    InMemoryTokenStorageAdapter,
)
from tezlify_studio.infrastructure.media.youtube_api_client_impl import YouTubeApiClientImpl
from tezlify_studio.infrastructure.scheduler.scheduler_service import PublishSchedulerService

from tezlify_studio.application.use_cases.import_video_use_case import ImportVideoUseCase
from tezlify_studio.application.use_cases.get_media_use_case import GetMediaUseCase
from tezlify_studio.application.use_cases.list_media_use_case import ListMediaUseCase
from tezlify_studio.application.use_cases.delete_media_use_case import DeleteMediaUseCase
from tezlify_studio.application.use_cases.get_system_status_use_case import GetSystemStatusUseCase
from tezlify_studio.application.use_cases.generate_youtube_auth_url_use_case import GenerateYouTubeAuthUrlUseCase
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import CompleteYouTubeAuthenticationUseCase
from tezlify_studio.application.use_cases.get_connected_youtube_account_use_case import GetConnectedYouTubeAccountUseCase
from tezlify_studio.application.use_cases.disconnect_youtube_account_use_case import DisconnectYouTubeAccountUseCase
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase
from tezlify_studio.application.use_cases.resume_youtube_upload_use_case import ResumeYouTubeUploadUseCase
from tezlify_studio.application.use_cases.cancel_youtube_upload_use_case import CancelYouTubeUploadUseCase
from tezlify_studio.application.use_cases.get_youtube_publish_status_use_case import GetYouTubePublishStatusUseCase
from tezlify_studio.application.use_cases.list_publish_records_use_case import ListPublishRecordsUseCase
from tezlify_studio.application.use_cases.create_scheduled_publish_use_case import (
    CreateScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.update_scheduled_publish_use_case import (
    UpdateScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.cancel_scheduled_publish_use_case import (
    CancelScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.get_scheduled_publish_use_case import (
    GetScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.list_scheduled_publishes_use_case import (
    ListScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.get_upcoming_publishes_use_case import (
    GetUpcomingPublishesUseCase,
)
from tezlify_studio.application.use_cases.retry_failed_scheduled_publish_use_case import (
    RetryFailedScheduledPublishUseCase,
)

# Creator Studio: platform-agnostic channel / analytics / comments use cases
from tezlify_studio.application.use_cases.list_platforms_use_case import ListPlatformsUseCase
from tezlify_studio.application.use_cases.get_channel_overview_use_case import GetChannelOverviewUseCase
from tezlify_studio.application.use_cases.list_channel_videos_use_case import ListChannelVideosUseCase
from tezlify_studio.application.use_cases.get_channel_video_use_case import GetChannelVideoUseCase
from tezlify_studio.application.use_cases.update_channel_video_use_case import UpdateChannelVideoUseCase
from tezlify_studio.application.use_cases.list_channel_playlists_use_case import ListChannelPlaylistsUseCase
from tezlify_studio.application.use_cases.list_video_categories_use_case import ListVideoCategoriesUseCase
from tezlify_studio.application.use_cases.get_channel_analytics_use_case import GetChannelAnalyticsUseCase
from tezlify_studio.application.use_cases.list_comments_use_case import ListCommentsUseCase
from tezlify_studio.application.use_cases.reply_to_comment_use_case import ReplyToCommentUseCase
from tezlify_studio.application.use_cases.set_comment_moderation_use_case import SetCommentModerationUseCase
from tezlify_studio.application.use_cases.get_dashboard_use_case import GetDashboardUseCase
from tezlify_studio.application.services.youtube_token_provider import YouTubeTokenProvider
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YouTubeCreatorApi

# Singleton instances
media_storage = LocalMediaStorage(settings.media_dir, settings.temp_dir)
video_probe = VideoProbeImpl()

# Strict Environment Isolation: InMemoryTokenStorageAdapter is strictly reserved for pytest / CI
_is_test_runner = os.environ.get("TEZLIFY_TEST_ENV") == "1" or "pytest" in sys.modules
token_storage: TokenStoragePort = (
    InMemoryTokenStorageAdapter() if _is_test_runner else KeychainTokenStorageAdapter(fallback_to_memory=False)
)
youtube_publisher = YouTubeApiClientImpl()

def get_repository(db: Session = Depends(get_db)) -> MediaRepositoryImpl:
    return MediaRepositoryImpl(db)

def get_social_account_repository(db: Session = Depends(get_db)) -> SocialAccountRepositoryImpl:
    return SocialAccountRepositoryImpl(db)

def get_publish_record_repository(db: Session = Depends(get_db)) -> PublishRecordRepositoryImpl:
    return PublishRecordRepositoryImpl(db)

def get_storage() -> LocalMediaStorage:
    return media_storage

def get_probe() -> VideoProbeImpl:
    return video_probe

def get_token_storage() -> TokenStoragePort:
    return token_storage

def get_youtube_publisher() -> YouTubeApiClientImpl:
    return youtube_publisher

# Media Use Cases
def get_import_use_case(
    repo: MediaRepositoryImpl = Depends(get_repository),
    storage: LocalMediaStorage = Depends(get_storage),
    probe: VideoProbeImpl = Depends(get_probe),
) -> ImportVideoUseCase:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    return ImportVideoUseCase(repo, storage, probe, max_upload_bytes=max_bytes)

def get_media_use_case(
    repo: MediaRepositoryImpl = Depends(get_repository),
) -> GetMediaUseCase:
    return GetMediaUseCase(repo)

def get_list_use_case(
    repo: MediaRepositoryImpl = Depends(get_repository),
) -> ListMediaUseCase:
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

# Publish Use Cases
def get_generate_youtube_auth_url_use_case(
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> GenerateYouTubeAuthUrlUseCase:
    return GenerateYouTubeAuthUrlUseCase(publisher)

def get_complete_youtube_auth_use_case(
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    storage: TokenStoragePort = Depends(get_token_storage),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> CompleteYouTubeAuthenticationUseCase:
    return CompleteYouTubeAuthenticationUseCase(account_repo, storage, publisher)

def get_connected_youtube_account_use_case(
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    storage: TokenStoragePort = Depends(get_token_storage),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> GetConnectedYouTubeAccountUseCase:
    return GetConnectedYouTubeAccountUseCase(account_repo, storage, publisher)

def get_disconnect_youtube_account_use_case(
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    storage: TokenStoragePort = Depends(get_token_storage),
) -> DisconnectYouTubeAccountUseCase:
    return DisconnectYouTubeAccountUseCase(account_repo, storage)

def _make_publish_repo_factory():
    def factory():
        db = SessionLocal()
        return PublishRecordRepositoryImpl(db), lambda: db.close()
    return factory

def get_publish_video_use_case(
    media_repo: MediaRepositoryImpl = Depends(get_repository),
    storage: LocalMediaStorage = Depends(get_storage),
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    token_store: TokenStoragePort = Depends(get_token_storage),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> PublishVideoToYouTubeUseCase:
    return PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=storage,
        account_repo=account_repo,
        publish_repo=publish_repo,
        token_storage=token_store,
        publisher=publisher,
        repo_factory=_make_publish_repo_factory(),
    )

def get_resume_upload_use_case(
    publish_use_case: PublishVideoToYouTubeUseCase = Depends(get_publish_video_use_case),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    media_repo: MediaRepositoryImpl = Depends(get_repository),
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> ResumeYouTubeUploadUseCase:
    return ResumeYouTubeUploadUseCase(
        publish_use_case=publish_use_case,
        publish_repo=publish_repo,
        media_repo=media_repo,
        account_repo=account_repo,
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

# Scheduler dependencies
def get_scheduled_publish_repository(db: Session = Depends(get_db)) -> ScheduledPublishRepositoryImpl:
    return ScheduledPublishRepositoryImpl(db)

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
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
    media_repo: MediaRepositoryImpl = Depends(get_repository),
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
) -> CreateScheduledPublishUseCase:
    return CreateScheduledPublishUseCase(sched_repo, media_repo, account_repo, publish_repo)

def get_update_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> UpdateScheduledPublishUseCase:
    return UpdateScheduledPublishUseCase(sched_repo)

def get_cancel_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> CancelScheduledPublishUseCase:
    return CancelScheduledPublishUseCase(sched_repo)

def get_get_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> GetScheduledPublishUseCase:
    return GetScheduledPublishUseCase(sched_repo)

def get_list_scheduled_publishes_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> ListScheduledPublishesUseCase:
    return ListScheduledPublishesUseCase(sched_repo)

def get_upcoming_publishes_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> GetUpcomingPublishesUseCase:
    return GetUpcomingPublishesUseCase(sched_repo)

def get_retry_scheduled_publish_use_case(
    sched_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> RetryFailedScheduledPublishUseCase:
    return RetryFailedScheduledPublishUseCase(sched_repo)

# ---------------------------------------------------------------------------
# Creator Studio Dependencies (platform-agnostic YouTube channel management)
# ---------------------------------------------------------------------------
_creator_http_client = httpx.Client(timeout=30.0)

def get_youtube_creator_api(
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    storage: TokenStoragePort = Depends(get_token_storage),
    publisher: YouTubeApiClientImpl = Depends(get_youtube_publisher),
) -> YouTubeCreatorApi:
    provider = YouTubeTokenProvider(account_repo, storage, publisher)
    return YouTubeCreatorApi(provider, client=_creator_http_client)

def get_list_platforms_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> ListPlatformsUseCase:
    return ListPlatformsUseCase(api)

def get_channel_overview_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> GetChannelOverviewUseCase:
    return GetChannelOverviewUseCase(api)

def get_list_channel_videos_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> ListChannelVideosUseCase:
    return ListChannelVideosUseCase(api)

def get_channel_video_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> GetChannelVideoUseCase:
    return GetChannelVideoUseCase(api)

def get_update_channel_video_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> UpdateChannelVideoUseCase:
    return UpdateChannelVideoUseCase(api)

def get_list_channel_playlists_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> ListChannelPlaylistsUseCase:
    return ListChannelPlaylistsUseCase(api)

def get_list_video_categories_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> ListVideoCategoriesUseCase:
    return ListVideoCategoriesUseCase(api)

def get_channel_analytics_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> GetChannelAnalyticsUseCase:
    return GetChannelAnalyticsUseCase(api, max_range_days=settings.analytics_max_range_days)

def get_list_comments_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> ListCommentsUseCase:
    return ListCommentsUseCase(api)

def get_reply_to_comment_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> ReplyToCommentUseCase:
    return ReplyToCommentUseCase(api)

def get_set_comment_moderation_use_case(
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
) -> SetCommentModerationUseCase:
    return SetCommentModerationUseCase(api)

def get_dashboard_use_case(
    account_repo: SocialAccountRepositoryImpl = Depends(get_social_account_repository),
    api: YouTubeCreatorApi = Depends(get_youtube_creator_api),
    publish_repo: PublishRecordRepositoryImpl = Depends(get_publish_record_repository),
    schedule_repo: ScheduledPublishRepositoryImpl = Depends(get_scheduled_publish_repository),
) -> GetDashboardUseCase:
    return GetDashboardUseCase(
        account_repo=account_repo,
        channel_port=api,
        analytics_port=api,
        publish_repo=publish_repo,
        schedule_repo=schedule_repo,
        default_range_days=settings.analytics_default_range_days,
        max_range_days=settings.analytics_max_range_days,
    )
