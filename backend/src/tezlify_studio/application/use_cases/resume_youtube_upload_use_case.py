import threading
from tezlify_studio.domain.enums.publish_status import PublishStatus
from tezlify_studio.domain.exceptions.media_exceptions import EntityNotFoundException, InvalidMediaFileException
from tezlify_studio.domain.exceptions.publish_exceptions import UploadSessionExpiredException
from tezlify_studio.application.ports.channel_access_provider_port import ChannelAccessProviderPort
from tezlify_studio.application.ports.channel_context_resolver_port import ChannelContextResolverPort
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.domain.exceptions.creator_exceptions import CreatorStudioException
from tezlify_studio.domain.value_objects.youtube_capabilities import CAPABILITY_UPLOAD
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase

class ResumeYouTubeUploadUseCase:
    def __init__(
        self,
        publish_use_case: PublishVideoToYouTubeUseCase,
        publish_repo: PublishRecordRepositoryPort,
        media_repo: MediaRepositoryPort,
        resolver: ChannelContextResolverPort,
        access_provider: ChannelAccessProviderPort,
        publisher: YouTubePublisherPort,
    ):
        self.publish_use_case = publish_use_case
        self.publish_repo = publish_repo
        self.media_repo = media_repo
        self.resolver = resolver
        self.access_provider = access_provider
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

        if not record.channel_id:
            record.transition_to(
                PublishStatus.REQUIRES_REAUTH,
                error_code="CHANNEL_UNRESOLVED",
                error_message=(
                    "Bu kaydın hangi kanala ait olduğu kesin değil. Yanlış kanala yükleme "
                    "yapmamak için devam ettirilmedi; videoyu hedef kanalı seçerek yeniden yayınlayın."
                ),
            )
            self.publish_repo.save(record)
            raise CreatorStudioException(
                "Bu yayın kaydının kanalı belirsiz (unresolved). Güvenli devam için kanal seçerek "
                "yeniden yayınlayın.",
                "CHANNEL_UNRESOLVED",
            )

        context = self.resolver.resolve(record.channel_id)
        capability_service = getattr(self.publish_use_case, "capability_service", None)
        if capability_service:
            capability_service.require(context.connection, CAPABILITY_UPLOAD)
        access = self.access_provider.get_access(context)
        self.publish_use_case._assert_token_binding(
            access.access_token, context.channel.channel_external_id, context.channel.id
        )
        access_token = access.access_token

        # 1. Query Google for last uploaded byte position
        if record.upload_session_uri:
            try:
                status_res = self.publisher.query_upload_status(
                    record.upload_session_uri,
                    record.total_bytes,
                )
                confirmed_bytes = int(status_res)
                finalized_data = getattr(status_res, "finalized_data", None)

                # Check if YouTube has already completed and finalized this upload
                if finalized_data and finalized_data.get("id"):
                    video_id = finalized_data["id"]
                    record.external_video_id = video_id
                    record.external_video_url = f"https://youtu.be/{video_id}"
                    record.update_progress(record.total_bytes, record.total_bytes)
                    self.publish_use_case._verify_and_finalize_processing(
                        record=record,
                        access_token=access_token,
                        repo=self.publish_repo,
                    )
                    return publish_record_to_dto(record)

                record.update_progress(confirmed_bytes, record.total_bytes)
                record.transition_to(PublishStatus.UPLOADING)
                record = self.publish_repo.save(record)
            except UploadSessionExpiredException:
                record.upload_session_uri = None
                record.uploaded_bytes = 0
                record.transition_to(
                    PublishStatus.FAILED,
                    error_code="SESSION_EXPIRED",
                    error_message="Google yükleme oturumunun süresi dolmuş. Yeni bir oturum başlatılmalıdır.",
                )
                self.publish_repo.save(record)
                raise
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
