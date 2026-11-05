from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata
from tezlify_studio.application.dto.media_dto import MediaAssetDTO, VideoMetadataDTO
from tezlify_studio.application.dto.publish_dto import SocialAccountDTO, PublishRecordDTO
from tezlify_studio.application.dto.schedule_dto import ScheduledPublishDTO

def metadata_to_dto(meta: VideoMetadata | None) -> VideoMetadataDTO | None:
    if not meta:
        return None
    return VideoMetadataDTO(
        duration_seconds=meta.duration_seconds,
        width=meta.width,
        height=meta.height,
        fps=meta.fps,
        video_codec=meta.video_codec,
        audio_codec=meta.audio_codec,
        aspect_ratio=meta.aspect_ratio,
        probe_source=meta.probe_source,
        resolution_label=meta.resolution_label,
    )

def media_asset_to_dto(asset: MediaAsset) -> MediaAssetDTO:
    return MediaAssetDTO(
        id=asset.id,
        filename=asset.filename,
        original_filename=asset.original_filename,
        file_path=asset.file_path,
        file_size_bytes=asset.file_size_bytes,
        mime_type=asset.mime_type,
        sha256_hash=asset.sha256_hash,
        status=asset.status.value,
        thumbnail_path=asset.thumbnail_path,
        created_at=asset.created_at.isoformat(),
        updated_at=asset.updated_at.isoformat(),
        metadata=metadata_to_dto(asset.metadata),
    )

def social_account_to_dto(account: SocialAccount) -> SocialAccountDTO:
    return SocialAccountDTO(
        id=account.id,
        platform=account.platform.value,
        account_name=account.account_name,
        channel_id=account.channel_id,
        channel_avatar_url=account.channel_avatar_url,
        is_active=account.is_active,
        is_token_valid=not account.is_token_expired(),
        created_at=account.created_at.isoformat(),
    )

def publish_record_to_dto(record: PublishRecord) -> PublishRecordDTO:
    return PublishRecordDTO(
        id=record.id,
        media_asset_id=record.media_asset_id,
        platform=record.platform.value,
        external_video_id=record.external_video_id,
        external_video_url=record.external_video_url,
        title=record.title,
        description=record.description,
        tags=record.tags or [],
        category_id=record.category_id,
        privacy_status=record.privacy_status.value,
        status=record.status.value,
        progress_percentage=record.progress_percentage,
        uploaded_bytes=record.uploaded_bytes,
        total_bytes=record.total_bytes,
        thumbnail_path=record.thumbnail_path,
        error_code=record.error_code,
        error_message=record.error_message,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        published_at=record.published_at.isoformat() if record.published_at else None,
        channel_id=record.channel_id,
        platform_connection_id=record.platform_connection_id,
        channel_attribution=record.channel_attribution,
    )

def scheduled_publish_to_dto(schedule: ScheduledPublish) -> ScheduledPublishDTO:
    return ScheduledPublishDTO(
        id=schedule.id,
        media_asset_id=schedule.media_asset_id,
        social_account_id=schedule.social_account_id,
        platform=schedule.platform.value,
        title=schedule.title,
        description=schedule.description,
        tags=schedule.tags or [],
        privacy_status=schedule.privacy_status.value,
        scheduled_at_utc=schedule.scheduled_at_utc.isoformat(),
        timezone=schedule.timezone,
        status=schedule.status.value,
        publish_record_id=schedule.publish_record_id,
        attempt_count=schedule.attempt_count,
        max_attempts=schedule.max_attempts,
        last_error_code=schedule.last_error_code,
        last_error_message=schedule.last_error_message,
        started_at=schedule.started_at.isoformat() if schedule.started_at else None,
        completed_at=schedule.completed_at.isoformat() if schedule.completed_at else None,
        created_at=schedule.created_at.isoformat(),
        updated_at=schedule.updated_at.isoformat(),
        version=schedule.version,
        channel_id=schedule.channel_id,
        platform_connection_id=schedule.platform_connection_id,
        channel_attribution=schedule.channel_attribution,
    )



