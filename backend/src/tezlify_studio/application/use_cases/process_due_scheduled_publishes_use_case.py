import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.enums.publish_status import PublishStatus
from tezlify_studio.domain.exceptions.publish_exceptions import (
    QuotaExceededException,
    AuthenticationRequiredException,
    SocialAccountNotFoundException,
)
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelBindingMismatchException,
    ChannelDisabledException,
    ChannelNotFoundException,
    ConnectionInactiveException,
    CreatorStudioException,
)
from tezlify_studio.domain.exceptions.media_exceptions import (
    EntityNotFoundException,
    InvalidMediaFileException,
)

logger = logging.getLogger(__name__)

class ProcessDueScheduledPublishesUseCase:
    """
    Core scheduler worker execution logic:
    - Finds due records.
    - Atomically claims each record using optimistic lock on version.
    - Invokes existing PublishVideoToYouTubeUseCase.
    - Classifies errors into permanent (fail immediately) vs transient (retry with backoff).
    - Prevents double uploads and guarantees idempotency.
    """
    def __init__(
        self,
        schedule_repo: ScheduledPublishRepositoryPort,
        publish_repo: PublishRecordRepositoryPort,
        publish_use_case: PublishVideoToYouTubeUseCase,
        retry_delay_minutes: int = 5,
        resume_use_case: Optional[Any] = None,
    ):
        self.schedule_repo = schedule_repo
        self.publish_repo = publish_repo
        self.publish_use_case = publish_use_case
        self.retry_delay_minutes = retry_delay_minutes
        self.resume_use_case = resume_use_case

    def execute(self, max_batch: int = 10) -> int:
        now_utc = datetime.now(timezone.utc)
        due_records = self.schedule_repo.get_due_records(now_utc=now_utc, limit=max_batch)
        processed_count = 0

        for schedule in due_records:
            # 1. Atomic claim check
            claimed = self.schedule_repo.claim_for_processing(
                schedule_id=schedule.id,
                expected_version=schedule.version,
            )
            if not claimed:
                logger.info("Schedule '%s' was already claimed or version changed, skipping.", schedule.id)
                continue

            # Reload domain entity in claimed PROCESSING state
            record = self.schedule_repo.get_by_id(schedule.id)
            if not record or record.status != ScheduleStatus.PROCESSING:
                continue

            processed_count += 1
            logger.info("Starting processing for scheduled publish '%s' (title: '%s')", record.id, record.title)

            if not record.channel_id:
                record.mark_failed(
                    error_code="CHANNEL_UNRESOLVED",
                    error_message=(
                        "Bu planın hangi kanala ait olduğu kesin değil. Yanlış kanala yükleme "
                        "yapmamak için otomatik yayın durduruldu; kanal seçerek yeniden planlayın."
                    ),
                )
                self.schedule_repo.save(record)
                continue

            # Idempotency Guard: Check if a publish record already exists for this schedule or media asset
            existing_pub = None
            if record.publish_record_id:
                existing_pub = self.publish_repo.get_by_id(record.publish_record_id)
            if not existing_pub:
                latest_pub = self.publish_repo.get_latest_by_media(
                    record.media_asset_id,
                    record.platform,
                    channel_id=record.channel_id,
                )
                if latest_pub and latest_pub.status == PublishStatus.PUBLISHED:
                    existing_pub = latest_pub

            # If already successfully published, avoid duplicate upload entirely
            if existing_pub and existing_pub.status == PublishStatus.PUBLISHED:
                record.mark_published(existing_pub.id)
                self.schedule_repo.save(record)
                logger.info(
                    "Schedule '%s' found existing completed publish '%s' (YT URL: %s). Resolved idempotently.",
                    record.id,
                    existing_pub.id,
                    existing_pub.external_video_url,
                )
                continue

            try:
                # If an interrupted upload exists with a session URI, resume it rather than starting over
                if existing_pub and existing_pub.status in (PublishStatus.PAUSED, PublishStatus.UPLOADING) and existing_pub.upload_session_uri and self.resume_use_case:
                    logger.info("Resuming existing interrupted upload session for schedule '%s'", record.id)
                    record.publish_record_id = existing_pub.id
                    self.schedule_repo.save(record)
                    publish_dto = self.resume_use_case.execute(existing_pub.id, async_upload=False)
                else:
                    # Prepare Publish Request DTO
                    publish_req = StartPublishRequestDTO(
                        media_asset_id=record.media_asset_id,
                        title=record.title,
                        description=record.description,
                        tags=record.tags,
                        privacy_status=record.privacy_status.value,
                        channel_id=record.channel_id,
                    )
                    # Synchronous chunked upload in this scheduler worker thread
                    publish_dto = self.publish_use_case.execute(publish_req, async_upload=False)
                    record.publish_record_id = publish_dto.id
                    self.schedule_repo.save(record)

                # Verify publish record status in DB
                db_pub = self.publish_repo.get_by_id(publish_dto.id)
                if db_pub and db_pub.status == PublishStatus.PUBLISHED:
                    record.mark_published(publish_dto.id)
                    self.schedule_repo.save(record)
                    logger.info("Successfully published scheduled video '%s' (YT URL: %s)", record.id, db_pub.external_video_url)
                elif db_pub and db_pub.status == PublishStatus.FAILED:
                    record.mark_failed(db_pub.error_code or "PUBLISH_FAILED", db_pub.error_message or "Upload failed")
                    self.schedule_repo.save(record)
                else:
                    # Job paused or still in progress
                    record.mark_paused("UPLOAD_PAUSED", "Video yüklemesi duraklatıldı.")
                    self.schedule_repo.save(record)

            except (
                QuotaExceededException,
                AuthenticationRequiredException,
                SocialAccountNotFoundException,
                ChannelBindingMismatchException,
                ChannelDisabledException,
                ChannelNotFoundException,
                ConnectionInactiveException,
                CreatorStudioException,
            ) as e:
                # Permanent credential or quota error - do not retry automatically
                logger.warning("Permanent error publishing scheduled '%s': %s", record.id, e)
                record.mark_failed(
                    error_code="PERMANENT_ERROR",
                    error_message=f"Kalıcı hata nedeniyle otomatik tekrar iptal edildi: {str(e)}",
                )
                self.schedule_repo.save(record)

            except (EntityNotFoundException, InvalidMediaFileException) as e:
                # Permanent file error
                logger.warning("Invalid media for scheduled '%s': %s", record.id, e)
                record.mark_failed(
                    error_code="INVALID_MEDIA",
                    error_message=f"Medya dosyası hatası: {str(e)}",
                )
                self.schedule_repo.save(record)

            except Exception as e:
                # Transient error (network glitch, socket error, 5xx)
                logger.error("Transient error during scheduled publish '%s': %s", record.id, e)
                if record.attempt_count < record.max_attempts:
                    delay_mins = self.retry_delay_minutes * record.attempt_count
                    next_attempt = datetime.now(timezone.utc) + timedelta(minutes=delay_mins)
                    record.scheduled_at_utc = next_attempt
                    record.transition_to(
                        ScheduleStatus.SCHEDULED,
                        error_code="TRANSIENT_RETRY",
                        error_message=f"Geçici hata ({str(e)}). Yeniden deneme {record.attempt_count}/{record.max_attempts} zamanı: {next_attempt.isoformat()}",
                    )
                    self.schedule_repo.save(record)
                    logger.info("Scheduled publish '%s' re-armed for retry at %s", record.id, next_attempt.isoformat())
                else:
                    record.mark_failed(
                        error_code="MAX_ATTEMPTS_EXCEEDED",
                        error_message=f"Maksimum deneme sınırına ({record.max_attempts}) ulaşıldı: {str(e)}",
                    )
                    self.schedule_repo.save(record)

        return processed_count
