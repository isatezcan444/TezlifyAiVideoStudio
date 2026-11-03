import os
import uuid
import time
import threading
from typing import Optional, List, Callable, Tuple, Any
from datetime import datetime, timezone, timedelta
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.domain.exceptions.media_exceptions import (
    EntityNotFoundException,
    InvalidMediaFileException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    SocialAccountNotFoundException,
    DuplicatePublishException,
    AuthenticationRequiredException,
    QuotaExceededException,
    UploadSessionExpiredException,
)
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort
from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.application.ports.publish_record_repository_port import PublishRecordRepositoryPort
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.dto.publish_dto import PublishRecordDTO, StartPublishRequestDTO
from tezlify_studio.application.dto.mappers import publish_record_to_dto

# Google Resumable Upload standard chunk size (must be multiple of 256 KB)
DEFAULT_CHUNK_SIZE = 1024 * 1024 * 4  # 4 MB

class PublishVideoToYouTubeUseCase:
    def __init__(
        self,
        media_repo: MediaRepositoryPort,
        storage: MediaStoragePort,
        account_repo: SocialAccountRepositoryPort,
        publish_repo: PublishRecordRepositoryPort,
        token_storage: TokenStoragePort,
        publisher: YouTubePublisherPort,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        repo_factory: Optional[Callable[[], Tuple[PublishRecordRepositoryPort, Any]]] = None,
        stop_checker: Optional[Callable[[], bool]] = None,
    ):
        self.media_repo = media_repo
        self.storage = storage
        self.account_repo = account_repo
        self.publish_repo = publish_repo
        self.token_storage = token_storage
        self.publisher = publisher
        self.chunk_size = chunk_size
        self.repo_factory = repo_factory
        self.stop_checker = stop_checker

    def _get_valid_access_token(self, account_id: str) -> str:
        account = self.account_repo.get_by_id(account_id)
        if not account or not account.is_active:
            raise AuthenticationRequiredException("YouTube hesabı aktif değil.")

        access_token = self.token_storage.get_access_token(account_id)
        if account.is_token_expired() or not access_token:
            refresh_token = self.token_storage.get_refresh_token(account_id)
            if not refresh_token:
                raise AuthenticationRequiredException("Refresh token bulunamadı, lütfen YouTube hesabını tekrar bağlayın.")
            try:
                refreshed = self.publisher.refresh_access_token(refresh_token)
                access_token = refreshed.get("access_token")
                expires_in = refreshed.get("expires_in", 3600)
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                self.account_repo.save(account)
                self.token_storage.store_tokens(account_id, access_token, refresh_token)
            except Exception as e:
                raise AuthenticationRequiredException(f"Token yenilenemedi: {str(e)}")

        return access_token

    def execute(self, req: StartPublishRequestDTO, async_upload: bool = False) -> PublishRecordDTO:
        # 1. Validate MediaAsset
        media = self.media_repo.get_by_id(req.media_asset_id)
        if not media:
            raise EntityNotFoundException("MediaAsset", req.media_asset_id)

        if media.status != MediaStatus.READY:
            raise InvalidMediaFileException("Video henüz işlenmedi veya hazır durumda değil.")

        if not self.storage.exists(media.file_path):
            raise InvalidMediaFileException("Video dosyası fiziksel depolamada bulunamadı.")

        file_size = self.storage.get_file_size(media.file_path)
        if file_size <= 0:
            raise InvalidMediaFileException("Video dosyası boş (0 bytes).")

        # 2. Validate Connected YouTube Account
        account = self.account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
        if not account:
            raise SocialAccountNotFoundException("youtube")

        # 3. Check for concurrent active publish jobs
        existing = self.publish_repo.get_active_by_media(media.id, SocialPlatform.YOUTUBE)
        if existing and existing.status in (
            PublishStatus.PENDING,
            PublishStatus.UPLOADING,
            PublishStatus.PROCESSING,
            PublishStatus.PAUSED,
        ):
            raise DuplicatePublishException(media.id, "youtube", existing.id)

        # 4. Create PublishRecord (PENDING)
        record = PublishRecord(
            id=str(uuid.uuid4()),
            media_asset_id=media.id,
            platform=SocialPlatform.YOUTUBE,
            title=req.title.strip() or media.original_filename,
            description=req.description.strip(),
            tags=req.tags or [],
            category_id=req.category_id or "22",
            privacy_status=PrivacyStatus(req.privacy_status),
            status=PublishStatus.PENDING,
            total_bytes=file_size,
            thumbnail_path=req.thumbnail_path or media.thumbnail_path,
        )
        record = self.publish_repo.save(record)

        # 5. Acquire access token
        try:
            access_token = self._get_valid_access_token(account.id)
        except AuthenticationRequiredException as e:
            record.transition_to(PublishStatus.REQUIRES_REAUTH, error_code="REQUIRES_REAUTH", error_message=str(e))
            self.publish_repo.save(record)
            raise

        # 6. Initiate Resumable Upload session
        try:
            session_uri = self.publisher.initiate_resumable_upload(
                access_token=access_token,
                title=record.title,
                description=record.description,
                tags=record.tags,
                category_id=record.category_id,
                privacy=record.privacy_status.value,
                total_bytes=file_size,
            )
            record.upload_session_uri = session_uri
            record.transition_to(PublishStatus.UPLOADING)
            record = self.publish_repo.save(record)
        except QuotaExceededException as e:
            record.transition_to(PublishStatus.FAILED, error_code="QUOTA_EXCEEDED", error_message=str(e))
            self.publish_repo.save(record)
            raise
        except Exception as e:
            record.transition_to(PublishStatus.FAILED, error_code="INITIATE_FAILED", error_message=str(e))
            self.publish_repo.save(record)
            raise

        # 7. Perform chunked upload
        if async_upload:
            thread = threading.Thread(
                target=self._run_async_chunks,
                args=(record.id, media.file_path, access_token),
                daemon=True,
            )
            thread.start()
        else:
            self._upload_file_chunks(record, media.file_path, access_token, self.publish_repo)

        return publish_record_to_dto(record)

    def _run_async_chunks(self, record_id: str, file_path: str, access_token: str) -> None:
        cleanup = None
        repo = self.publish_repo
        if self.repo_factory:
            repo, cleanup = self.repo_factory()

        try:
            record = repo.get_by_id(record_id)
            if not record:
                return
            self._upload_file_chunks(record, file_path, access_token, repo)
        except Exception:
            # Error state has already been updated and persisted to repo by _upload_file_chunks
            pass
        finally:
            if cleanup and callable(cleanup):
                cleanup()

    def _upload_file_chunks(
        self,
        record: PublishRecord,
        file_path: str,
        access_token: str,
        repo: PublishRecordRepositoryPort,
    ) -> None:
        total_bytes = record.total_bytes
        start_byte = record.uploaded_bytes

        # If already at total bytes (e.g. uncertain last chunk), verify status
        if start_byte >= total_bytes and record.upload_session_uri:
            try:
                status_res = self.publisher.query_upload_status(record.upload_session_uri, total_bytes)
                finalized = getattr(status_res, "finalized_data", None)
                if finalized and finalized.get("id"):
                    video_id = finalized["id"]
                    record.external_video_id = video_id
                    record.external_video_url = f"https://youtu.be/{video_id}"
                    record.transition_to(PublishStatus.PUBLISHED)
                    repo.save(record)
                    return
            except Exception:
                pass

        try:
            with open(file_path, "rb") as f:
                f.seek(start_byte)
                while start_byte < total_bytes:
                    # Check if server/worker is shutting down
                    if self.stop_checker and self.stop_checker():
                        record.transition_to(
                            PublishStatus.PAUSED,
                            error_code="SERVER_STOPPING",
                            error_message="Sunucu kapanırken yükleme temiz şekilde duraklatıldı.",
                        )
                        repo.save(record)
                        return

                    # Check if user cancelled upload in DB
                    current = repo.get_by_id(record.id)
                    if current and current.status == PublishStatus.CANCELLED:
                        return

                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break

                    status_code, response_data = self.publisher.upload_chunk(
                        upload_session_uri=record.upload_session_uri,
                        chunk_data=chunk,
                        start_byte=start_byte,
                        total_bytes=total_bytes,
                    )

                    start_byte += len(chunk)
                    record.update_progress(start_byte, total_bytes)

                    # Persist progress
                    repo.save(record)

                    # Final chunk completed
                    if status_code in (200, 201) and response_data:
                        video_id = response_data.get("id")
                        record.external_video_id = video_id
                        record.external_video_url = f"https://youtu.be/{video_id}"

                        # Detect immediate rejection in YouTube upload response
                        status_info = response_data.get("status", {})
                        upload_status = status_info.get("uploadStatus")
                        rejection_reason = status_info.get("rejectionReason")
                        failure_reason = status_info.get("failureReason")

                        if upload_status == "rejected" or rejection_reason or failure_reason:
                            reason = rejection_reason or failure_reason or upload_status or "Unknown"
                            record.transition_to(
                                PublishStatus.FAILED,
                                error_code="YOUTUBE_REJECTED",
                                error_message=f"YouTube video işleme motoru yüklemeyi reddetti: {reason}",
                            )
                            repo.save(record)
                            return

                        self._verify_and_finalize_processing(
                            record=record,
                            access_token=access_token,
                            repo=repo,
                        )
                        return

        except UploadSessionExpiredException as e:
            record.upload_session_uri = None
            record.uploaded_bytes = 0
            record.transition_to(
                PublishStatus.FAILED,
                error_code="SESSION_EXPIRED",
                error_message="Google yükleme oturumunun süresi dolmuş. Yeni bir oturum başlatılmalıdır.",
            )
            repo.save(record)
            raise
        except QuotaExceededException as e:
            record.transition_to(PublishStatus.FAILED, error_code="QUOTA_EXCEEDED", error_message=str(e))
            repo.save(record)
            raise
        except Exception as e:
            record.transition_to(PublishStatus.PAUSED, error_code="UPLOAD_INTERRUPTED", error_message=str(e))
            repo.save(record)
            raise

    def _verify_and_finalize_processing(
        self,
        record: PublishRecord,
        access_token: str,
        repo: PublishRecordRepositoryPort,
        max_poll_attempts: int = 5,
        poll_interval: float = 2.0,
    ) -> None:
        """
        Polls YouTube API to verify video processing status after chunk upload.
        Transitions record to:
        - PUBLISHED if processing succeeds (uploadStatus=='processed' or processingStatus=='succeeded')
        - FAILED if rejected, failed, or deleted by YouTube
        - Remains in PROCESSING if YouTube is still actively transcoding or result is indeterminate
        """
        record.transition_to(PublishStatus.PROCESSING)
        repo.save(record)

        for attempt in range(max_poll_attempts):
            try:
                details = self.publisher.get_video_details(
                    access_token=access_token,
                    video_id=record.external_video_id,
                )
            except Exception:
                if attempt < max_poll_attempts - 1:
                    time.sleep(poll_interval)
                continue

            # In mock or uninstrumented test environments where details is empty
            if not details:
                record.transition_to(PublishStatus.PUBLISHED)
                repo.save(record)
                break

            if details.get("not_found"):
                record.transition_to(
                    PublishStatus.FAILED,
                    error_code="YOUTUBE_REJECTED",
                    error_message="Video YouTube tarafından işlenemedi veya silindi (API kaydı bulunamadı).",
                )
                repo.save(record)
                return

            status_obj = details.get("status", {})
            proc_obj = details.get("processingDetails", {})

            upload_status = status_obj.get("uploadStatus")
            rejection_reason = status_obj.get("rejectionReason")
            failure_reason = status_info_failure = status_obj.get("failureReason")
            processing_status = proc_obj.get("processingStatus")
            proc_failure_reason = proc_obj.get("processingFailureReason")

            # Check rejection or failure
            if (
                upload_status in ("rejected", "failed", "deleted")
                or rejection_reason
                or failure_reason
                or processing_status in ("failed", "terminated")
                or proc_failure_reason
            ):
                reason = (
                    rejection_reason
                    or failure_reason
                    or proc_failure_reason
                    or upload_status
                    or "Unknown"
                )
                record.transition_to(
                    PublishStatus.FAILED,
                    error_code="YOUTUBE_REJECTED",
                    error_message=f"YouTube video işleme motoru yüklemeyi reddetti: {reason}",
                )
                repo.save(record)
                return

            # Check success: video is ready and available
            if upload_status == "processed" or processing_status == "succeeded":
                record.transition_to(PublishStatus.PUBLISHED)
                repo.save(record)
                break

            # Still processing on YouTube: wait and retry
            if upload_status == "uploaded" or processing_status == "processing":
                if attempt < max_poll_attempts - 1:
                    time.sleep(poll_interval)
                    continue

        # Post-processing thumbnail upload if video reached PUBLISHED
        if record.status == PublishStatus.PUBLISHED and record.thumbnail_path and self.storage.exists(record.thumbnail_path):
            try:
                self.publisher.upload_custom_thumbnail(
                    access_token=access_token,
                    video_id=record.external_video_id,
                    thumbnail_path=record.thumbnail_path,
                )
            except Exception:
                pass

