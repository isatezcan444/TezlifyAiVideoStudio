import threading
from tezlify_studio.domain.enums.publish_status import PublishStatus
from tezlify_studio.domain.exceptions.media_exceptions import EntityNotFoundException, InvalidMediaFileException
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase

class ResumeYouTubeUploadUseCase:
    def __init__(
        self,
        publish_use_case: PublishVideoToYouTubeUseCase,
        publish_repo: PublishRecordRepositoryPort,
        media_repo: MediaRepositoryPort,
        account_repo: SocialAccountRepositoryPort,
        publisher: YouTubePublisherPort,
    ):
        self.publish_use_case = publish_use_case
        self.publish_repo = publish_repo
        self.media_repo = media_repo
        self.account_repo = account_repo
        self.publisher = publisher

    def execute(self, publish_id: str, async_upload: bool = False) -> PublishRecordDTO:
        record = self.publish_repo.get_by_id(publish_id)
        if not record:
            raise EntityNotFoundException("PublishRecord", publish_id)

        if record.status in (PublishStatus.PUBLISHED, PublishStatus.CANCELLED):
            raise InvalidMediaFileException(f"Yayınlama işlemi '{record.status.value}' durumunda olduğu için devam ettirilemez.")

        media = self.media_repo.get_by_id(record.media_asset_id)
        if not media or not self.publish_use_case.storage.exists(media.file_path):
            raise InvalidMediaFileException("Video dosyası diskte bulunamadı.")

        account = self.account_repo.get_active_by_platform(record.platform)
        if not account:
            record.transition_to(PublishStatus.REQUIRES_REAUTH)
            self.publish_repo.save(record)
            raise EntityNotFoundException("SocialAccount", record.platform.value)

        access_token = self.publish_use_case._get_valid_access_token(account.id)

        # 1. Query Google for last uploaded byte position
        if record.upload_session_uri:
            try:
                confirmed_bytes = self.publisher.query_upload_status(
                    record.upload_session_uri,
                    record.total_bytes,
                )
                record.update_progress(confirmed_bytes, record.total_bytes)
                record.transition_to(PublishStatus.UPLOADING)
                record = self.publish_repo.save(record)
            except Exception:
                pass

        # 2. Continue chunk upload
        if async_upload:
            thread = threading.Thread(
                target=self.publish_use_case._run_async_chunks,
                args=(record.id, media.file_path, access_token),
                daemon=True,
            )
            thread.start()
        else:
            self.publish_use_case._upload_file_chunks(record, media.file_path, access_token, self.publish_repo)

        return publish_record_to_dto(record)
