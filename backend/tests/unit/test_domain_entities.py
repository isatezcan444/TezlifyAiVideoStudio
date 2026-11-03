import pytest
from datetime import datetime, timezone
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.import_record import ImportRecord
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata
from tezlify_studio.domain.enums.media_status import MediaStatus, ImportSource
from tezlify_studio.domain.exceptions.media_exceptions import (
    EntityNotFoundException,
    DuplicateMediaException,
    InvalidMediaFileException,
)

def test_media_asset_creation_and_ready_transition():
    asset = MediaAsset(
        id="test-123",
        filename="123_video.mp4",
        original_filename="video.mp4",
        file_path="/tmp/video.mp4",
        file_size_bytes=1024,
        mime_type="video/mp4",
        sha256_hash="abc123hash",
        status=MediaStatus.PENDING,
    )
    assert asset.status == MediaStatus.PENDING
    assert asset.metadata is None

    meta = VideoMetadata(
        duration_seconds=12.5,
        width=1920,
        height=1080,
        fps=30.0,
        video_codec="h264",
        audio_codec="aac",
        aspect_ratio="1.78:1",
    )
    asset.mark_ready(metadata=meta, thumbnail_path="/tmp/thumb.jpg")

    assert asset.status == MediaStatus.READY
    assert asset.metadata == meta
    assert asset.metadata.resolution_label == "1920x1080"
    assert asset.thumbnail_path == "/tmp/thumb.jpg"

def test_media_asset_mark_failed():
    asset = MediaAsset(
        id="test-fail",
        filename="fail.mp4",
        original_filename="fail.mp4",
        file_path="/tmp/fail.mp4",
        file_size_bytes=500,
        mime_type="video/mp4",
        sha256_hash="failhash",
    )
    asset.mark_failed()
    assert asset.status == MediaStatus.FAILED

def test_domain_exceptions():
    nf = EntityNotFoundException("MediaAsset", "id-999")
    assert "MediaAsset with id 'id-999' was not found" in str(nf)

    dup = DuplicateMediaException("hash-xyz", "existing-id-1")
    assert "existing-id-1" in str(dup)

    inv = InvalidMediaFileException("Corrupt format")
    assert "Corrupt format" in str(inv)

