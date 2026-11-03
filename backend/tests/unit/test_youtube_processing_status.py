import pytest
from unittest.mock import MagicMock
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import PublishVideoToYouTubeUseCase

def make_test_use_case(mock_publisher):
    mock_media_repo = MagicMock()
    mock_storage = MagicMock()
    mock_storage.exists.return_value = False
    mock_account_repo = MagicMock()
    mock_publish_repo = MagicMock()
    mock_token_storage = MagicMock()

    use_case = PublishVideoToYouTubeUseCase(
        media_repo=mock_media_repo,
        storage=mock_storage,
        account_repo=mock_account_repo,
        publish_repo=mock_publish_repo,
        token_storage=mock_token_storage,
        publisher=mock_publisher,
    )
    return use_case

def test_processing_transitions_to_published_on_success():
    mock_publisher = MagicMock()
    mock_publisher.get_video_details.return_value = {
        "id": "vid_succ_123",
        "status": {"uploadStatus": "processed", "privacyStatus": "private"},
        "processingDetails": {"processingStatus": "succeeded"},
    }
    use_case = make_test_use_case(mock_publisher)

    record = PublishRecord(
        id="rec_succ",
        media_asset_id="asset_1",
        platform=SocialPlatform.YOUTUBE,
        external_video_id="vid_succ_123",
        status=PublishStatus.UPLOADING,
        total_bytes=1000,
        uploaded_bytes=1000,
    )
    repo = MagicMock()

    use_case._verify_and_finalize_processing(
        record=record,
        access_token="tok_123",
        repo=repo,
        max_poll_attempts=2,
        poll_interval=0.01,
    )

    assert record.status == PublishStatus.PUBLISHED
    repo.save.assert_called()

def test_processing_transitions_to_failed_on_rejection():
    mock_publisher = MagicMock()
    mock_publisher.get_video_details.return_value = {
        "id": "vid_rej_123",
        "status": {
            "uploadStatus": "rejected",
            "rejectionReason": "codec",
            "failureReason": "codec",
        },
        "processingDetails": {"processingStatus": "failed", "processingFailureReason": "transcodingFailed"},
    }
    use_case = make_test_use_case(mock_publisher)

    record = PublishRecord(
        id="rec_rej",
        media_asset_id="asset_1",
        platform=SocialPlatform.YOUTUBE,
        external_video_id="vid_rej_123",
        status=PublishStatus.UPLOADING,
        total_bytes=1000,
        uploaded_bytes=1000,
    )
    repo = MagicMock()

    use_case._verify_and_finalize_processing(
        record=record,
        access_token="tok_123",
        repo=repo,
        max_poll_attempts=2,
        poll_interval=0.01,
    )

    assert record.status == PublishStatus.FAILED
    assert record.error_code == "YOUTUBE_REJECTED"
    assert "codec" in record.error_message

def test_processing_transitions_to_failed_on_remote_not_found():
    mock_publisher = MagicMock()
    mock_publisher.get_video_details.return_value = {"not_found": True, "items": []}
    use_case = make_test_use_case(mock_publisher)

    record = PublishRecord(
        id="rec_nf",
        media_asset_id="asset_1",
        platform=SocialPlatform.YOUTUBE,
        external_video_id="vid_purged_123",
        status=PublishStatus.UPLOADING,
        total_bytes=1000,
        uploaded_bytes=1000,
    )
    repo = MagicMock()

    use_case._verify_and_finalize_processing(
        record=record,
        access_token="tok_123",
        repo=repo,
        max_poll_attempts=2,
        poll_interval=0.01,
    )

    assert record.status == PublishStatus.FAILED
    assert record.error_code == "YOUTUBE_REJECTED"

def test_processing_remains_processing_when_transcoding_in_progress():
    mock_publisher = MagicMock()
    mock_publisher.get_video_details.return_value = {
        "id": "vid_proc_123",
        "status": {"uploadStatus": "uploaded", "privacyStatus": "private"},
        "processingDetails": {"processingStatus": "processing"},
    }
    use_case = make_test_use_case(mock_publisher)

    record = PublishRecord(
        id="rec_proc",
        media_asset_id="asset_1",
        platform=SocialPlatform.YOUTUBE,
        external_video_id="vid_proc_123",
        status=PublishStatus.UPLOADING,
        total_bytes=1000,
        uploaded_bytes=1000,
    )
    repo = MagicMock()

    use_case._verify_and_finalize_processing(
        record=record,
        access_token="tok_123",
        repo=repo,
        max_poll_attempts=2,
        poll_interval=0.01,
    )

    # Must stay in PROCESSING because YouTube is still actively transcoding!
    assert record.status == PublishStatus.PROCESSING
