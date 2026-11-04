import os
import sys
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
# Stage 4: AI Animation Studio Dependencies
# ---------------------------------------------------------------------------
from tezlify_studio.infrastructure.persistence.repositories.studio_project_repository_impl import (
    StudioProjectRepositoryImpl,
)
from tezlify_studio.infrastructure.ai.template_story_planner_impl import TemplateStoryPlannerImpl
from tezlify_studio.infrastructure.ai.ollama_story_planner_impl import OllamaStoryPlannerImpl
from tezlify_studio.application.use_cases.create_studio_project_use_case import (
    CreateStudioProjectUseCase,
)
from tezlify_studio.application.use_cases.generate_story_scene_graph_use_case import (
    GenerateStorySceneGraphUseCase,
)
from tezlify_studio.application.use_cases.get_studio_project_use_case import (
    GetStudioProjectUseCase,
)
from tezlify_studio.application.use_cases.list_studio_projects_use_case import (
    ListStudioProjectsUseCase,
)
from tezlify_studio.application.use_cases.update_studio_project_use_case import (
    UpdateStudioProjectUseCase,
)
from tezlify_studio.application.use_cases.delete_studio_project_use_case import (
    DeleteStudioProjectUseCase,
)

template_story_planner_singleton = TemplateStoryPlannerImpl()
ollama_story_planner_singleton = OllamaStoryPlannerImpl(fallback_planner=template_story_planner_singleton)

def get_studio_project_repository(db: Session = Depends(get_db)) -> StudioProjectRepositoryImpl:
    return StudioProjectRepositoryImpl(db)

def get_template_story_planner() -> TemplateStoryPlannerImpl:
    return template_story_planner_singleton

def get_ollama_story_planner() -> OllamaStoryPlannerImpl:
    return ollama_story_planner_singleton

def get_create_studio_project_use_case(
    repo: StudioProjectRepositoryImpl = Depends(get_studio_project_repository),
) -> CreateStudioProjectUseCase:
    return CreateStudioProjectUseCase(repo)

def get_generate_story_use_case(
    template_planner: TemplateStoryPlannerImpl = Depends(get_template_story_planner),
    ollama_planner: OllamaStoryPlannerImpl = Depends(get_ollama_story_planner),
) -> GenerateStorySceneGraphUseCase:
    return GenerateStorySceneGraphUseCase(template_planner, ollama_planner)

def get_studio_project_use_case(
    repo: StudioProjectRepositoryImpl = Depends(get_studio_project_repository),
) -> GetStudioProjectUseCase:
    return GetStudioProjectUseCase(repo)

def get_list_studio_projects_use_case(
    repo: StudioProjectRepositoryImpl = Depends(get_studio_project_repository),
) -> ListStudioProjectsUseCase:
    return ListStudioProjectsUseCase(repo)

def get_update_studio_project_use_case(
    repo: StudioProjectRepositoryImpl = Depends(get_studio_project_repository),
) -> UpdateStudioProjectUseCase:
    return UpdateStudioProjectUseCase(repo)

def get_delete_studio_project_use_case(
    repo: StudioProjectRepositoryImpl = Depends(get_studio_project_repository),
) -> DeleteStudioProjectUseCase:
    return DeleteStudioProjectUseCase(repo)

# Character & Asset Studio (Stage 4.2)
from tezlify_studio.infrastructure.persistence.repositories.character_repository_impl import (
    CharacterRepositoryImpl,
)
from tezlify_studio.infrastructure.persistence.repositories.studio_asset_repository_impl import (
    StudioAssetRepositoryImpl,
)
from tezlify_studio.infrastructure.blender.blender_asset_generator_impl import (
    BlenderAssetGeneratorImpl,
)
from tezlify_studio.application.use_cases.create_character_use_case import (
    CreateCharacterUseCase,
)
from tezlify_studio.application.use_cases.get_character_use_case import (
    GetCharacterUseCase,
)
from tezlify_studio.application.use_cases.list_characters_use_case import (
    ListCharactersUseCase,
)
from tezlify_studio.application.use_cases.update_character_use_case import (
    UpdateCharacterUseCase,
)
from tezlify_studio.application.use_cases.delete_character_use_case import (
    DeleteCharacterUseCase,
)
from tezlify_studio.application.use_cases.get_studio_asset_use_case import (
    GetStudioAssetUseCase,
)
from tezlify_studio.application.use_cases.list_studio_assets_use_case import (
    ListStudioAssetsUseCase,
)
from tezlify_studio.application.use_cases.seed_builtin_assets_use_case import (
    SeedBuiltinAssetsUseCase,
)

blender_asset_generator_singleton = BlenderAssetGeneratorImpl()

def get_character_repository(db: Session = Depends(get_db)) -> CharacterRepositoryImpl:
    return CharacterRepositoryImpl(db)

def get_studio_asset_repository(db: Session = Depends(get_db)) -> StudioAssetRepositoryImpl:
    return StudioAssetRepositoryImpl(db)

def get_blender_asset_generator() -> BlenderAssetGeneratorImpl:
    return blender_asset_generator_singleton

def get_create_character_use_case(
    repo: CharacterRepositoryImpl = Depends(get_character_repository),
    blender: BlenderAssetGeneratorImpl = Depends(get_blender_asset_generator),
) -> CreateCharacterUseCase:
    return CreateCharacterUseCase(repo, blender)

def get_character_use_case(
    repo: CharacterRepositoryImpl = Depends(get_character_repository),
) -> GetCharacterUseCase:
    return GetCharacterUseCase(repo)

def get_list_characters_use_case(
    repo: CharacterRepositoryImpl = Depends(get_character_repository),
) -> ListCharactersUseCase:
    return ListCharactersUseCase(repo)

def get_update_character_use_case(
    repo: CharacterRepositoryImpl = Depends(get_character_repository),
    blender: BlenderAssetGeneratorImpl = Depends(get_blender_asset_generator),
) -> UpdateCharacterUseCase:
    return UpdateCharacterUseCase(repo, blender)

def get_delete_character_use_case(
    repo: CharacterRepositoryImpl = Depends(get_character_repository),
) -> DeleteCharacterUseCase:
    return DeleteCharacterUseCase(repo)

def get_studio_asset_use_case(
    repo: StudioAssetRepositoryImpl = Depends(get_studio_asset_repository),
) -> GetStudioAssetUseCase:
    return GetStudioAssetUseCase(repo)

def get_list_studio_assets_use_case(
    repo: StudioAssetRepositoryImpl = Depends(get_studio_asset_repository),
) -> ListStudioAssetsUseCase:
    return ListStudioAssetsUseCase(repo)

def get_seed_builtin_assets_use_case(
    char_repo: CharacterRepositoryImpl = Depends(get_character_repository),
    asset_repo: StudioAssetRepositoryImpl = Depends(get_studio_asset_repository),
    blender: BlenderAssetGeneratorImpl = Depends(get_blender_asset_generator),
) -> SeedBuiltinAssetsUseCase:
    return SeedBuiltinAssetsUseCase(char_repo, asset_repo, blender)

# ==========================================
# Render Engine & Jobs (Stage 4.3)
# ==========================================
from tezlify_studio.infrastructure.persistence.repositories.render_job_repository_impl import RenderJobRepositoryImpl
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import BlenderAnimationEngineImpl
from tezlify_studio.application.use_cases.start_project_render_use_case import StartProjectRenderUseCase
from tezlify_studio.application.use_cases.get_render_job_use_case import GetRenderJobUseCase
from tezlify_studio.application.use_cases.list_project_renders_use_case import ListProjectRendersUseCase
from tezlify_studio.application.use_cases.execute_render_job_use_case import ExecuteRenderJobUseCase

blender_animation_engine_singleton = BlenderAnimationEngineImpl()

def get_render_job_repository(db: Session = Depends(get_db)) -> RenderJobRepositoryImpl:
    return RenderJobRepositoryImpl(db)

def get_blender_animation_engine() -> BlenderAnimationEngineImpl:
    return blender_animation_engine_singleton

def get_execute_render_job_use_case(
    engine: BlenderAnimationEngineImpl = Depends(get_blender_animation_engine),
) -> ExecuteRenderJobUseCase:
    return ExecuteRenderJobUseCase(engine)

def get_start_project_render_use_case(
    project_repo: StudioProjectRepositoryImpl = Depends(get_studio_project_repository),
    job_repo: RenderJobRepositoryImpl = Depends(get_render_job_repository),
    execute_worker: ExecuteRenderJobUseCase = Depends(get_execute_render_job_use_case),
) -> StartProjectRenderUseCase:
    return StartProjectRenderUseCase(project_repo, job_repo, execute_worker)

def get_render_job_use_case(
    repo: RenderJobRepositoryImpl = Depends(get_render_job_repository),
) -> GetRenderJobUseCase:
    return GetRenderJobUseCase(repo)

def get_list_project_renders_use_case(
    repo: RenderJobRepositoryImpl = Depends(get_render_job_repository),
) -> ListProjectRendersUseCase:
    return ListProjectRendersUseCase(repo)



