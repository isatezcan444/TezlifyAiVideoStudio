"""Stage 6.5 acceptance: missing capabilities must stop writes before any call.

The fake ports below raise if the application reaches an upload or comment port
without the required grant. A green run therefore proves the guard runs first,
not merely that the API returns an error after a request was attempted.
"""

from typing import Optional

import pytest

from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.application.use_cases.reply_to_comment_use_case import (
    ReplyToCommentUseCase,
)
from tezlify_studio.application.use_cases.set_comment_moderation_use_case import (
    SetCommentModerationUseCase,
)
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import (
    InsufficientScopeException,
)
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    SCOPE_COMMENTS,
    SCOPE_OPENID,
    SCOPE_UPLOAD,
)

_BASE_SCOPES = [SCOPE_OPENID, "https://www.googleapis.com/auth/youtube.readonly"]


def _connection(scopes, connection_id="conn_1"):
    return PlatformConnection(
        id=connection_id,
        platform=SocialPlatform.YOUTUBE,
        account_external_id=f"google:{connection_id}",
        account_display_name="Test Hesabı",
        granted_scopes=list(scopes),
    )


def _context(connection):
    return ChannelContext(
        channel=PlatformChannel(
            id="local_ch_1",
            platform_connection_id=connection.id,
            platform=SocialPlatform.YOUTUBE,
            channel_external_id="UC_REAL",
            channel_name="Kanal",
        ),
        connection=connection,
    )


class _Resolver:
    def __init__(self, connection):
        self.connection = connection

    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        return _context(self.connection)


class _ExplodingGateway:
    def __init__(self):
        self.bind_called = False

    def bind(self, context):
        self.bind_called = True
        raise AssertionError("gateway bind must not run without the required grant")


class _MediaRepo:
    def __init__(self):
        self.media = MediaAsset(
            id="m1",
            filename="video.mp4",
            original_filename="video.mp4",
            file_path="/tmp/video.mp4",
            file_size_bytes=1024,
            mime_type="video/mp4",
            sha256_hash="hash",
            status=MediaStatus.READY,
        )

    def get_by_id(self, media_id):
        return self.media


class _Storage:
    def exists(self, path):
        return True

    def get_file_size(self, path):
        return 1024


class _ExplodingAccessProvider:
    def __init__(self):
        self.called = False

    def get_access(self, context):
        self.called = True
        raise AssertionError("token access must not run without upload permission")


class _ExplodingPublisher:
    def initiate_resumable_upload(self, *args, **kwargs):
        raise AssertionError("upload must not start without upload permission")


def _upload_use_case(connection):
    access = _ExplodingAccessProvider()
    use_case = PublishVideoToYouTubeUseCase(
        media_repo=_MediaRepo(),
        storage=_Storage(),
        resolver=_Resolver(connection),
        access_provider=access,
        publish_repo=None,
        publisher=_ExplodingPublisher(),
        capability_service=YouTubeCapabilityService(),
    )
    return use_case, access


def test_upload_stops_before_token_or_api_without_upload_scope():
    use_case, access = _upload_use_case(_connection(_BASE_SCOPES))

    with pytest.raises(InsufficientScopeException) as exc:
        use_case.execute(
            StartPublishRequestDTO(
                media_asset_id="m1", title="Test", channel_id="local_ch_1"
            )
        )

    assert exc.value.capability == "upload"
    assert exc.value.required_scope == SCOPE_UPLOAD
    assert access.called is False


def test_upload_gate_does_not_borrow_another_connections_scope():
    granted = _connection(_BASE_SCOPES + [SCOPE_UPLOAD], connection_id="conn_granted")
    other = _connection(_BASE_SCOPES, connection_id="conn_other")
    assert YouTubeCapabilityService().can(granted, "upload") is True

    use_case, access = _upload_use_case(other)
    with pytest.raises(InsufficientScopeException):
        use_case.execute(
            StartPublishRequestDTO(
                media_asset_id="m1", title="Test", channel_id="local_ch_1"
            )
        )
    assert access.called is False


def test_comment_reply_stops_before_api_without_force_ssl_scope():
    gateway = _ExplodingGateway()
    use_case = ReplyToCommentUseCase(
        _Resolver(_connection(_BASE_SCOPES)), gateway, YouTubeCapabilityService()
    )

    with pytest.raises(InsufficientScopeException) as exc:
        use_case.execute("comment_1", "Teşekkürler")

    assert exc.value.capability == "comments"
    assert exc.value.required_scope == SCOPE_COMMENTS
    assert gateway.bind_called is False


def test_comment_moderation_stops_before_api_without_force_ssl_scope():
    gateway = _ExplodingGateway()
    use_case = SetCommentModerationUseCase(
        _Resolver(_connection(_BASE_SCOPES)), gateway, YouTubeCapabilityService()
    )

    with pytest.raises(InsufficientScopeException):
        use_case.execute("comment_1", "rejected")

    assert gateway.bind_called is False
