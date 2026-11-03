from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata
from tezlify_studio.application.dto.media_dto import MediaAssetDTO, VideoMetadataDTO

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

