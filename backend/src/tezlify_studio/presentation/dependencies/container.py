from fastapi import Depends
from sqlalchemy.orm import Session
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.database import get_db
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import MediaRepositoryImpl
from tezlify_studio.infrastructure.media.local_media_storage import LocalMediaStorage
from tezlify_studio.infrastructure.media.video_probe_impl import VideoProbeImpl
from tezlify_studio.application.use_cases.import_video_use_case import ImportVideoUseCase
from tezlify_studio.application.use_cases.get_media_use_case import GetMediaUseCase
from tezlify_studio.application.use_cases.list_media_use_case import ListMediaUseCase
from tezlify_studio.application.use_cases.delete_media_use_case import DeleteMediaUseCase
from tezlify_studio.application.use_cases.get_system_status_use_case import GetSystemStatusUseCase

# Singleton storage and probe instances
media_storage = LocalMediaStorage(settings.media_dir, settings.temp_dir)
video_probe = VideoProbeImpl()

def get_repository(db: Session = Depends(get_db)) -> MediaRepositoryImpl:
    return MediaRepositoryImpl(db)

def get_storage() -> LocalMediaStorage:
    return media_storage

def get_probe() -> VideoProbeImpl:
    return video_probe

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

