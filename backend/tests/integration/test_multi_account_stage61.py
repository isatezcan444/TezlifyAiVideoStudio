"""Stage 6.1 multi-account / multi-channel scenario coverage.

Everything here runs against in-memory fake ports (no real YouTube calls, no
Keychain writes) except the migration tests, which use throw-away SQLite files.
"""
import os
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from tezlify_studio.application.dto.schedule_dto import CreateScheduledPublishDTO
from tezlify_studio.application.dto.publish_dto import StartPublishRequestDTO
from tezlify_studio.application.ports.analytics_port import AnalyticsPort
from tezlify_studio.application.ports.channel_port import ChannelPort
from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.application.ports.comment_port import CommentPort
from tezlify_studio.application.ports.creator_gateway_port import (
    CreatorGatewayPort,
    CreatorSession,
)
from tezlify_studio.application.ports.media_repository_port import MediaRepositoryPort
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import (
    UploadStatusResult,
    YouTubePublisherPort,
)
from tezlify_studio.application.services.channel_context_service import (
    ChannelContextService,
)
from tezlify_studio.application.services.connection_token_provider import (
    ConnectionTokenProvider,
)
from tezlify_studio.application.use_cases.complete_youtube_authentication_use_case import (
    CompleteYouTubeAuthenticationUseCase,
)
from tezlify_studio.application.use_cases.create_scheduled_publish_use_case import (
    CreateScheduledPublishUseCase,
)
from tezlify_studio.application.use_cases.disconnect_platform_connection_use_case import (
    DisconnectPlatformConnectionUseCase,
)
from tezlify_studio.application.use_cases.get_dashboard_use_case import (
    GetDashboardUseCase,
)
from tezlify_studio.application.use_cases.list_platforms_use_case import (
    ListPlatformsUseCase,
)
from tezlify_studio.application.use_cases.oauth_session_store import (
    oauth_session_store,
)
from tezlify_studio.application.use_cases.process_due_scheduled_publishes_use_case import (
    ProcessDueScheduledPublishesUseCase,
)
from tezlify_studio.application.use_cases.publish_video_to_youtube_use_case import (
    PublishVideoToYouTubeUseCase,
)
from tezlify_studio.domain.entities.channel_selection import ChannelSelection
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.entities.publish_record import PublishRecord
from tezlify_studio.domain.entities.scheduled_publish import ScheduledPublish
from tezlify_studio.domain.enums.connection_status import ConnectionStatus
from tezlify_studio.domain.enums.media_status import MediaStatus
from tezlify_studio.domain.enums.publish_status import (
    PrivacyStatus,
    PublishStatus,
    SocialPlatform,
)
from tezlify_studio.domain.enums.schedule_status import ScheduleStatus
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelBindingMismatchException,
    ChannelDisabledException,
    ChannelNotFoundException,
    ConnectionInactiveException,
    DuplicateOAuthCallbackException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
)
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    ChannelPlaylist,
    ChannelProfile,
    ChannelVideo,
)
from tezlify_studio.infrastructure.platform_catalog import PlatformCatalog

REPO_ROOT = Path(__file__).resolve().parents[3]
SCOPES = (
    "https://www.googleapis.com/auth/youtube "
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.readonly"
)


# ---------------------------------------------------------------------------
# In-memory ports
# ---------------------------------------------------------------------------
class FakeConnectionRepo(PlatformConnectionRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, PlatformConnection] = {}

    def save(self, connection: PlatformConnection) -> PlatformConnection:
        self.items[connection.id] = connection
        return connection

    def get_by_id(self, connection_id: str) -> Optional[PlatformConnection]:
        return self.items.get(connection_id)

    def get_by_platform_account(
        self, platform: str, account_external_id: str
    ) -> Optional[PlatformConnection]:
        for connection in self.items.values():
            if (
                connection.platform.value == platform
                and connection.account_external_id == account_external_id
            ):
                return connection
        return None

    def list_by_platform(
        self, platform: str, include_disconnected: bool = False
    ) -> List[PlatformConnection]:
        return [
            item
            for item in self.items.values()
            if item.platform.value == platform
            and (include_disconnected or item.is_active)
        ]

    def list_all(
        self, include_disconnected: bool = False
    ) -> List[PlatformConnection]:
        return [
            item
            for item in self.items.values()
            if include_disconnected or item.is_active
        ]

    def count(self) -> int:
        return len(self.items)

    def delete(self, connection_id: str) -> bool:
        return self.items.pop(connection_id, None) is not None


class FakeChannelRepo(PlatformChannelRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, PlatformChannel] = {}

    def save(self, channel: PlatformChannel) -> PlatformChannel:
        self.items[channel.id] = channel
        return channel

    def get_by_id(self, channel_id: str) -> Optional[PlatformChannel]:
        return self.items.get(channel_id)

    def get_by_connection_external(
        self, connection_id: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        for channel in self.items.values():
            if (
                channel.platform_connection_id == connection_id
                and channel.channel_external_id == channel_external_id
            ):
                return channel
        return None

    def find_by_external_id(
        self, platform: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        for channel in self.items.values():
            if (
                channel.platform.value == platform
                and channel.channel_external_id == channel_external_id
            ):
                return channel
        return None

    def list_by_connection(self, connection_id: str) -> List[PlatformChannel]:
        return [
            item
            for item in self.items.values()
            if item.platform_connection_id == connection_id
        ]

    def list_enabled(self, platform: Optional[str] = None) -> List[PlatformChannel]:
        return [
            item
            for item in self.items.values()
            if item.is_enabled and (not platform or item.platform.value == platform)
        ]

    def set_enabled(
        self, channel_id: str, enabled: bool
    ) -> Optional[PlatformChannel]:
        channel = self.items.get(channel_id)
        if channel:
            channel.is_enabled = enabled
        return channel

    def count(self, enabled_only: bool = True) -> int:
        return len([item for item in self.items.values() if item.is_enabled or not enabled_only])

    def delete(self, channel_id: str) -> bool:
        return self.items.pop(channel_id, None) is not None


class FakeSelectionRepo(ChannelSelectionRepositoryPort):
    def __init__(self) -> None:
        self.selection = ChannelSelection()

    def get(self) -> ChannelSelection:
        return self.selection

    def save(self, selection: ChannelSelection) -> ChannelSelection:
        self.selection = selection
        return selection


class FakeTokenStorage(TokenStoragePort):
    """Stands in for the macOS Keychain; values never leave this process."""

    def __init__(self) -> None:
        self.tokens: Dict[str, Dict[str, Optional[str]]] = {}
        self.deleted: set[str] = set()

    def store_tokens(
        self, account_id: str, access_token: str, refresh_token: Optional[str] = None
    ) -> None:
        current = self.tokens.get(account_id, {})
        self.tokens[account_id] = {
            "access": access_token,
            "refresh": refresh_token if refresh_token is not None else current.get("refresh"),
        }
        self.deleted.discard(account_id)

    def get_access_token(self, account_id: str) -> Optional[str]:
        return self.tokens.get(account_id, {}).get("access")

    def get_refresh_token(self, account_id: str) -> Optional[str]:
        return self.tokens.get(account_id, {}).get("refresh")

    def delete_tokens(self, account_id: str) -> None:
        self.tokens.pop(account_id, None)
        self.deleted.add(account_id)


class FakePublisher(YouTubePublisherPort):
    """Deterministic fake of the YouTube API with per-token visibility."""

    def __init__(self) -> None:
        self.code_tokens: Dict[str, str] = {}
        self.access_refresh: Dict[str, str] = {}
        self.access_profiles: Dict[str, List[Dict[str, Any]]] = {}
        self.access_identity: Dict[str, Dict[str, Any]] = {}
        self.refresh_log: List[str] = []
        self.uploads: List[Dict[str, Any]] = []
        self.session_video_ids: Dict[str, str] = {}

    def register_account(
        self,
        code: str,
        access_token: str,
        refresh_token: str,
        identity: Dict[str, Any],
        profiles: List[Dict[str, Any]],
    ) -> None:
        self.code_tokens[code] = access_token
        self.access_refresh[access_token] = refresh_token
        self.access_identity[access_token] = dict(identity)
        self.access_profiles[access_token] = [dict(profile) for profile in profiles]

    def generate_auth_url(
        self, state: str, code_challenge: str, redirect_uri: Optional[str] = None
    ) -> str:
        return f"https://accounts.google.test/o/oauth2/auth?state={state}"

    def exchange_code_for_tokens(
        self, code: str, code_verifier: str, redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        access = self.code_tokens.get(code)
        if not access:
            raise AuthenticationRequiredException("unknown authorization code")
        return {
            "access_token": access,
            "refresh_token": self.access_refresh.get(access),
            "expires_in": 3600,
            "scope": SCOPES,
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        if refresh_token not in self.access_refresh.values():
            raise AuthenticationRequiredException("unknown refresh token")
        self.refresh_log.append(refresh_token)
        return {"access_token": f"refreshed::{refresh_token}", "expires_in": 3600}

    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        profiles = self.access_profiles.get(access_token) or []
        return dict(profiles[0]) if profiles else {}

    def list_channel_profiles(self, access_token: str) -> List[Dict[str, Any]]:
        return [dict(profile) for profile in self.access_profiles.get(access_token, [])]

    def get_account_identity(self, access_token: str) -> Dict[str, Any]:
        return dict(self.access_identity.get(access_token, {}))

    def list_authorized_channel_ids(self, access_token: str) -> Optional[List[str]]:
        if access_token not in self.access_profiles:
            return None
        return [profile["channel_id"] for profile in self.access_profiles[access_token]]

    def initiate_resumable_upload(
        self,
        access_token: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str,
        privacy: str,
        total_bytes: int,
    ) -> str:
        uri = f"https://upload.youtube.test/session/{len(self.uploads)}"
        video_id = f"yt_video_{len(self.uploads) + 1}"
        self.uploads.append(
            {"access_token": access_token, "title": title, "uri": uri, "video_id": video_id}
        )
        self.session_video_ids[uri] = video_id
        return uri

    def upload_chunk(
        self,
        upload_session_uri: str,
        chunk_data: bytes,
        start_byte: int,
        total_bytes: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        return 200, {"id": self.session_video_ids.get(upload_session_uri, "yt_unknown")}

    def query_upload_status(self, upload_session_uri: str, total_bytes: int) -> int:
        return UploadStatusResult(0)

    def upload_custom_thumbnail(
        self, access_token: str, video_id: str, thumbnail_path: str
    ) -> bool:
        return True

    def get_video_details(self, access_token: str, video_id: str) -> Dict[str, Any]:
        return {}


class FakeMediaRepo(MediaRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, MediaAsset] = {}

    def save(self, asset: MediaAsset) -> MediaAsset:
        self.items[asset.id] = asset
        return asset

    def get_by_id(self, asset_id: str) -> Optional[MediaAsset]:
        return self.items.get(asset_id)

    def get_by_hash(self, sha256_hash: str) -> Optional[MediaAsset]:
        return next((item for item in self.items.values() if item.sha256_hash == sha256_hash), None)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[MediaAsset]:
        return list(self.items.values())[offset : offset + limit]

    def count(self) -> int:
        return len(self.items)

    def delete(self, asset_id: str) -> bool:
        return self.items.pop(asset_id, None) is not None

    def save_import_record(self, record):
        return record


class FakeStorage(MediaStoragePort):
    def exists(self, path: str) -> bool:
        return True

    def get_file_size(self, path: str) -> int:
        return os.path.getsize(path)

    def save_stream(self, stream, destination_filename, chunk_size=1048576, max_bytes=None):
        return (destination_filename, 4096, "fake_hash")

    def delete_file(self, path: str) -> bool:
        return True

    def open_range_stream(self, file_path, start, end, chunk_size=524288):
        yield b"0" * (end - start + 1)


class FakePublishRepo(PublishRecordRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, PublishRecord] = {}

    def save(self, record: PublishRecord) -> PublishRecord:
        self.items[record.id] = record
        return record

    def get_by_id(self, record_id: str) -> Optional[PublishRecord]:
        return self.items.get(record_id)

    @staticmethod
    def _active(record: PublishRecord) -> bool:
        return record.status in (
            PublishStatus.PENDING,
            PublishStatus.AUTHENTICATING,
            PublishStatus.UPLOADING,
            PublishStatus.PROCESSING,
            PublishStatus.PAUSED,
        )

    def get_active_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[PublishRecord]:
        for record in self.items.values():
            if record.media_asset_id != media_id or record.platform != platform:
                continue
            if channel_id and record.channel_id != channel_id:
                continue
            if self._active(record):
                return record
        return None

    def get_latest_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[PublishRecord]:
        matches = [
            record
            for record in self.items.values()
            if record.media_asset_id == media_id
            and record.platform == platform
            and (not channel_id or record.channel_id == channel_id)
        ]
        return max(matches, key=lambda item: item.created_at, default=None)

    def list_by_platform(
        self,
        platform: SocialPlatform,
        limit: int = 50,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> List[PublishRecord]:
        matches = [
            record
            for record in self.items.values()
            if record.platform == platform and (not channel_id or record.channel_id == channel_id)
        ]
        matches.sort(key=lambda item: item.created_at, reverse=True)
        return matches[offset : offset + limit]

    def count_by_channel(self, channel_id: str) -> int:
        return len([item for item in self.items.values() if item.channel_id == channel_id])

    def fail_pending_for_connection(
        self, connection_id: str, error_code: str, error_message: str
    ) -> int:
        affected = 0
        for record in self.items.values():
            if record.platform_connection_id != connection_id or not self._active(record):
                continue
            record.status = PublishStatus.FAILED
            record.error_code = error_code
            record.error_message = error_message
            affected += 1
        return affected

    def list_all(
        self, limit: int = 50, offset: int = 0, channel_id: Optional[str] = None
    ) -> List[PublishRecord]:
        matches = [
            item
            for item in self.items.values()
            if not channel_id or item.channel_id == channel_id
        ]
        return matches[offset : offset + limit]

    def get_in_flight_records(self) -> List[PublishRecord]:
        return [item for item in self.items.values() if self._active(item)]

    def count(self, channel_id: Optional[str] = None) -> int:
        return len(
            [item for item in self.items.values() if not channel_id or item.channel_id == channel_id]
        )

    def delete(self, record_id: str) -> bool:
        return self.items.pop(record_id, None) is not None


class FakeScheduleRepo(ScheduledPublishRepositoryPort):
    def __init__(self) -> None:
        self.items: Dict[str, ScheduledPublish] = {}

    def save(self, record: ScheduledPublish) -> ScheduledPublish:
        self.items[record.id] = record
        return record

    def get_by_id(self, schedule_id: str) -> Optional[ScheduledPublish]:
        return self.items.get(schedule_id)

    def get_due_records(
        self, now_utc: datetime, limit: int = 10
    ) -> List[ScheduledPublish]:
        due = [
            item
            for item in self.items.values()
            if item.status == ScheduleStatus.SCHEDULED and item.scheduled_at_utc <= now_utc
        ]
        return sorted(due, key=lambda item: item.scheduled_at_utc)[:limit]

    def get_in_flight_processing_records(self) -> List[ScheduledPublish]:
        return [item for item in self.items.values() if item.status == ScheduleStatus.PROCESSING]

    def get_active_by_media(
        self, media_id: str, platform: SocialPlatform, channel_id: Optional[str] = None
    ) -> Optional[ScheduledPublish]:
        for item in self.items.values():
            if item.media_asset_id != media_id or item.platform != platform:
                continue
            if channel_id and item.channel_id != channel_id:
                continue
            if item.status in (ScheduleStatus.SCHEDULED, ScheduleStatus.PROCESSING):
                return item
        return None

    def list_all(
        self,
        status: Optional[ScheduleStatus] = None,
        limit: int = 100,
        offset: int = 0,
        channel_id: Optional[str] = None,
    ) -> List[ScheduledPublish]:
        matches = [
            item
            for item in self.items.values()
            if (not status or item.status == status)
            and (not channel_id or item.channel_id == channel_id)
        ]
        return matches[offset : offset + limit]

    def list_upcoming(
        self, now_utc: datetime, limit: int = 20, channel_id: Optional[str] = None
    ) -> List[ScheduledPublish]:
        matches = [
            item
            for item in self.items.values()
            if item.status == ScheduleStatus.SCHEDULED
            and item.scheduled_at_utc > now_utc
            and (not channel_id or item.channel_id == channel_id)
        ]
        return sorted(matches, key=lambda item: item.scheduled_at_utc)[:limit]

    def fail_pending_for_connection(
        self, connection_id: str, error_code: str, error_message: str
    ) -> int:
        affected = 0
        for item in self.items.values():
            if item.platform_connection_id != connection_id:
                continue
            if item.status not in (
                ScheduleStatus.SCHEDULED,
                ScheduleStatus.PROCESSING,
                ScheduleStatus.PAUSED,
            ):
                continue
            item.status = ScheduleStatus.FAILED
            item.last_error_code = error_code
            item.last_error_message = error_message
            item.version += 1
            affected += 1
        return affected

    def claim_for_processing(self, schedule_id: str, expected_version: int) -> bool:
        item = self.items.get(schedule_id)
        if (
            not item
            or item.status != ScheduleStatus.SCHEDULED
            or item.version != expected_version
        ):
            return False
        item.status = ScheduleStatus.PROCESSING
        item.version += 1
        item.attempt_count += 1
        item.started_at = datetime.now(timezone.utc)
        return True

    def count(
        self,
        status: Optional[ScheduleStatus] = None,
        channel_id: Optional[str] = None,
    ) -> int:
        return len(
            [
                item
                for item in self.items.values()
                if (not status or item.status == status)
                and (not channel_id or item.channel_id == channel_id)
            ]
        )

    def delete(self, schedule_id: str) -> bool:
        return self.items.pop(schedule_id, None) is not None


# ---------------------------------------------------------------------------
# Fake creator gateway (dashboard isolation)
# ---------------------------------------------------------------------------
class FakeChannelPort(ChannelPort):
    def __init__(self, profile: ChannelProfile) -> None:
        self.profile = profile

    def get_channel(self) -> ChannelProfile:
        return self.profile

    def list_videos(self, max_results: int = 25, page_token: Optional[str] = None) -> Dict[str, Any]:
        return {"items": [{"video_id": f"{self.profile.channel_id}_v1"}]}

    def get_video(self, video_id: str) -> ChannelVideo:
        return ChannelVideo(video_id=video_id, title="video")

    def update_video(self, video_id: str, changes: Dict[str, Any]) -> ChannelVideo:
        return ChannelVideo(video_id=video_id, title="video")

    def list_playlists(self, max_results: int = 25) -> List[ChannelPlaylist]:
        return []

    def list_video_categories(self) -> List[Dict[str, str]]:
        return []


class FakeAnalyticsPort(AnalyticsPort):
    def __init__(self, views: int) -> None:
        self.views = views

    def query(
        self,
        date_range,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        return AnalyticsResult(
            available=True,
            totals={"views": self.views},
            metrics=list(metrics or []),
            dimensions=list(dimensions or []),
        )


class FakeCommentsPort(CommentPort):
    def list_comments(self, video_id=None, max_results=25, page_token=None):
        return []

    def reply_to_comment(self, parent_comment_id: str, text: str):
        raise AssertionError("this scenario must not write comments")

    def set_moderation_status(self, comment_id: str, status: str):
        raise AssertionError("this scenario must not write comments")


class FakeGateway(CreatorGatewayPort):
    def __init__(self) -> None:
        self.bound: List[str] = []

    def list_platforms(self):
        return PlatformCatalog().list_platforms()

    def bind(self, context: ChannelContext) -> CreatorSession:
        self.bound.append(context.external_channel_id)
        profile = ChannelProfile(
            channel_id=context.external_channel_id,
            title=context.channel.channel_name,
        )
        return CreatorSession(
            channel=FakeChannelPort(profile),
            analytics=FakeAnalyticsPort(views=100 if context.external_channel_id == "UC_A1" else 900),
            comments=FakeCommentsPort(),
            access=ChannelAccess(
                platform=context.channel.platform,
                channel_id=context.channel_id,
                external_channel_id=context.external_channel_id,
                connection_id=context.connection_id,
                access_token="fake",
            ),
        )


# ---------------------------------------------------------------------------
# Stack helpers
# ---------------------------------------------------------------------------
@dataclass
class Stack:
    connections: FakeConnectionRepo
    channels: FakeChannelRepo
    selection: FakeSelectionRepo
    tokens: FakeTokenStorage
    publisher: FakePublisher
    complete: CompleteYouTubeAuthenticationUseCase
    resolver: ChannelContextService
    access: ConnectionTokenProvider

    def connect(self, code: str):
        state, _ = oauth_session_store.create_session()
        return self.complete.execute(code, state)


def build_stack() -> Stack:
    connections = FakeConnectionRepo()
    channels = FakeChannelRepo()
    selection = FakeSelectionRepo()
    tokens = FakeTokenStorage()
    publisher = FakePublisher()
    return Stack(
        connections=connections,
        channels=channels,
        selection=selection,
        tokens=tokens,
        publisher=publisher,
        complete=CompleteYouTubeAuthenticationUseCase(
            connection_repo=connections,
            channel_repo=channels,
            selection_repo=selection,
            token_storage=tokens,
            publisher=publisher,
        ),
        resolver=ChannelContextService(connections, channels, selection),
        access=ConnectionTokenProvider(connections, tokens, publisher),
    )


def profile(
    channel_id: str,
    title: str,
    handle: Optional[str] = None,
    subscribers: Optional[int] = 10,
) -> Dict[str, Any]:
    return {
        "channel_id": channel_id,
        "channel_title": title,
        "custom_url": handle,
        "avatar_url": f"https://img.test/{channel_id}.png",
        "description": f"{title} description",
        "subscriber_count": subscribers,
        "uploads_playlist_id": f"UU_{channel_id}",
    }


def register_account(
    publisher: FakePublisher,
    code: str,
    access: str,
    refresh: str,
    subject: str,
    name: str,
    profiles: List[Dict[str, Any]],
) -> None:
    publisher.register_account(
        code=code,
        access_token=access,
        refresh_token=refresh,
        identity={"sub": subject, "name": name, "email": f"{subject}@example.test"},
        profiles=profiles,
    )


def connect_two_accounts(stack: Stack) -> Tuple[Any, Any]:
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Channel A1", "@a1")],
    )
    register_account(
        stack.publisher,
        "code-b",
        "access-b",
        "refresh-b",
        "google-sub-b",
        "Account B",
        [profile("UC_B1", "Channel B1", "@b1")],
    )
    dto_a = stack.connect("code-a")
    dto_b = stack.connect("code-b")
    return dto_a, dto_b


def add_media(media_repo: FakeMediaRepo, tmp_path: Path) -> MediaAsset:
    path = tmp_path / "video.mp4"
    path.write_bytes(b"x" * 4096)
    media = MediaAsset(
        id=f"media_{uuid.uuid4().hex[:8]}",
        filename="video.mp4",
        original_filename="video.mp4",
        file_path=str(path),
        file_size_bytes=4096,
        mime_type="video/mp4",
        sha256_hash=f"hash_{uuid.uuid4().hex}",
        status=MediaStatus.READY,
    )
    return media_repo.save(media)


def pending_publish(channel: PlatformChannel, media_id: str) -> PublishRecord:
    return PublishRecord(
        id=f"pub_{uuid.uuid4().hex[:8]}",
        media_asset_id=media_id,
        channel_id=channel.id,
        platform_connection_id=channel.platform_connection_id,
        channel_attribution="exact",
        title="pending",
        status=PublishStatus.PENDING,
    )


def pending_schedule(
    channel: PlatformChannel, media_id: str, when: datetime
) -> ScheduledPublish:
    return ScheduledPublish(
        id=f"sched_{uuid.uuid4().hex[:8]}",
        media_asset_id=media_id,
        channel_id=channel.id,
        platform_connection_id=channel.platform_connection_id,
        channel_attribution="exact",
        title="scheduled",
        scheduled_at_utc=when,
        status=ScheduleStatus.SCHEDULED,
    )


class MisroutingResolver:
    """Simulates a bug that pairs channel B with connection A's token."""

    def __init__(self, channel: PlatformChannel, connection: PlatformConnection) -> None:
        self.context = ChannelContext(channel=channel, connection=connection)

    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        return self.context


# ---------------------------------------------------------------------------
# §13 scenarios
# ---------------------------------------------------------------------------
def test_connect_first_google_account_creates_isolated_connection():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Channel A1")],
    )

    dto = stack.connect("code-a")

    assert stack.connections.count() == 1
    assert dto.account_external_id == "google:google-sub-a"
    assert dto.account_display_name == "Account A"
    assert dto.connection_status == "active"
    assert dto.channel_count == 1
    assert dto.channels[0].channel_external_id == "UC_A1"
    assert dto.channels[0].is_primary is True

    connection = stack.connections.get_by_id(dto.id)
    assert connection is not None
    assert connection.token_reference == f"youtube.connection.{dto.id}"
    assert stack.tokens.get_access_token(connection.token_reference) == "access-a"
    assert stack.tokens.get_refresh_token(connection.token_reference) == "refresh-a"
    assert stack.selection.get().active_channel_id == dto.channels[0].id


def test_second_google_account_does_not_overwrite_first():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)

    assert stack.connections.count() == 2
    assert dto_a.id != dto_b.id
    assert dto_a.account_display_name == "Account A"
    assert dto_b.account_display_name == "Account B"

    stored_a = stack.connections.get_by_id(dto_a.id)
    stored_b = stack.connections.get_by_id(dto_b.id)
    assert stored_a.is_active and stored_b.is_active
    assert {stored_a.account_external_id, stored_b.account_external_id} == {
        "google:google-sub-a",
        "google:google-sub-b",
    }
    assert len(stack.channels.list_by_connection(dto_a.id)) == 1
    assert len(stack.channels.list_by_connection(dto_b.id)) == 1
    # Adding B must not steal A's active channel.
    assert stack.selection.get().active_channel_id == dto_a.channels[0].id


def test_tokens_are_isolated_per_connection():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)

    conn_a = stack.connections.get_by_id(dto_a.id)
    conn_b = stack.connections.get_by_id(dto_b.id)
    assert conn_a.token_reference != conn_b.token_reference
    assert stack.tokens.get_access_token(conn_a.token_reference) == "access-a"
    assert stack.tokens.get_access_token(conn_b.token_reference) == "access-b"

    access_a = stack.access.get_access(stack.resolver.resolve(dto_a.channels[0].id))
    access_b = stack.access.get_access(stack.resolver.resolve(dto_b.channels[0].id))
    assert access_a.access_token == "access-a"
    assert access_b.access_token == "access-b"
    assert access_a.connection_id == dto_a.id
    assert access_b.connection_id == dto_b.id
    assert stack.publisher.uploads == []


def test_multiple_channels_under_one_google_account():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [
            profile("UC_A1", "Main Channel", "@main"),
            profile("UC_A2", "Brand Channel", "@brand", subscribers=None),
        ],
    )

    dto = stack.connect("code-a")

    assert dto.channel_count == 2
    names = {channel.channel_external_id: channel for channel in dto.channels}
    assert set(names) == {"UC_A1", "UC_A2"}
    assert names["UC_A1"].is_primary is True
    assert names["UC_A2"].is_primary is False
    assert names["UC_A2"].channel_handle == "@brand"
    assert stack.channels.count(enabled_only=True) == 2


def test_global_channel_list_covers_every_connection():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main Channel"), profile("UC_A2", "Brand Channel")],
    )
    register_account(
        stack.publisher,
        "code-b",
        "access-b",
        "refresh-b",
        "google-sub-b",
        "Account B",
        [profile("UC_B1", "B Channel")],
    )
    stack.connect("code-a")
    stack.connect("code-b")

    contexts = stack.resolver.list_contexts()
    assert [context.external_channel_id for context in contexts] == [
        "UC_A1",
        "UC_A2",
        "UC_B1",
    ]
    assert all(context.connection.is_active for context in contexts)


def test_channel_switch_persists_and_resolves_selected_channel():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Main Channel"), profile("UC_A2", "Brand Channel")],
    )
    register_account(
        stack.publisher,
        "code-b",
        "access-b",
        "refresh-b",
        "google-sub-b",
        "Account B",
        [profile("UC_B1", "B Channel")],
    )
    dto_a = stack.connect("code-a")
    dto_b = stack.connect("code-b")
    brand = next(item for item in dto_a.channels if item.channel_external_id == "UC_A2")

    stack.resolver.select(brand.id)
    assert stack.selection.get().active_channel_id == brand.id
    assert stack.resolver.resolve().external_channel_id == "UC_A2"

    stack.resolver.select(dto_b.channels[0].id)
    assert stack.selection.get().active_channel_id == dto_b.channels[0].id
    assert stack.resolver.resolve().external_channel_id == "UC_B1"


def test_dashboard_data_is_scoped_to_the_selected_channel():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    publish_repo = FakePublishRepo()
    schedule_repo = FakeScheduleRepo()

    channel_a = stack.channels.get_by_id(dto_a.channels[0].id)
    channel_b = stack.channels.get_by_id(dto_b.channels[0].id)
    for channel, media_id in ((channel_a, "m_a1"), (channel_a, "m_a2"), (channel_b, "m_b1")):
        publish_repo.save(
            PublishRecord(
                id=f"pub_{uuid.uuid4().hex[:8]}",
                media_asset_id=media_id,
                channel_id=channel.id,
                platform_connection_id=channel.platform_connection_id,
                channel_attribution="exact",
                title=media_id,
                status=PublishStatus.PUBLISHED,
            )
        )
    schedule_repo.save(
        pending_schedule(
            channel_b, "m_b1", datetime.now(timezone.utc) + timedelta(hours=2)
        )
    )

    gateway = FakeGateway()
    use_case = GetDashboardUseCase(stack.resolver, gateway, publish_repo, schedule_repo)

    snapshot_a = use_case.execute(channel_id=channel_a.id)
    assert snapshot_a.connected is True
    assert snapshot_a.channel_context["channel_id"] == channel_a.id
    assert snapshot_a.local_counts["scope"] == "channel"
    assert snapshot_a.local_counts["total_publish_records"] == 2
    assert {item["channel_id"] for item in snapshot_a.recent_publishes} == {channel_a.id}
    assert snapshot_a.upcoming_schedules == []
    assert gateway.bound[-1] == "UC_A1"
    assert snapshot_a.analytics.totals["views"] == 100

    snapshot_b = use_case.execute(channel_id=channel_b.id)
    assert snapshot_b.channel_context["channel_id"] == channel_b.id
    assert snapshot_b.local_counts["total_publish_records"] == 1
    assert {item["channel_id"] for item in snapshot_b.recent_publishes} == {channel_b.id}
    assert [item["channel_id"] for item in snapshot_b.upcoming_schedules] == [channel_b.id]
    assert gateway.bound[-1] == "UC_B1"
    assert snapshot_b.analytics.totals["views"] == 900


def test_upload_refuses_channel_not_authorized_for_connection(tmp_path):
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    channel_a = stack.channels.get_by_id(dto_a.channels[0].id)
    channel_b = stack.channels.get_by_id(dto_b.channels[0].id)
    connection_a = stack.connections.get_by_id(dto_a.id)

    media_repo = FakeMediaRepo()
    media = add_media(media_repo, tmp_path)
    publish_repo = FakePublishRepo()
    use_case = PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=FakeStorage(),
        resolver=MisroutingResolver(channel_b, connection_a),
        access_provider=stack.access,
        publish_repo=publish_repo,
        publisher=stack.publisher,
    )

    with pytest.raises(ChannelBindingMismatchException):
        use_case.execute(
            StartPublishRequestDTO(media_asset_id=media.id, title="wrong channel")
        )

    assert stack.publisher.uploads == []
    assert publish_repo.count() == 0
    # Sanity: the real channel is authorized for its own connection token.
    assert stack.publisher.list_authorized_channel_ids("access-a") == ["UC_A1"]
    assert stack.publisher.list_authorized_channel_ids("access-b") == ["UC_B1"]
    assert channel_a.channel_external_id == "UC_A1"


def test_upload_uses_target_channel_token_not_other_account(tmp_path):
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    channel_b = stack.channels.get_by_id(dto_b.channels[0].id)
    media_repo = FakeMediaRepo()
    media = add_media(media_repo, tmp_path)
    publish_repo = FakePublishRepo()
    use_case = PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=FakeStorage(),
        resolver=stack.resolver,
        access_provider=stack.access,
        publish_repo=publish_repo,
        publisher=stack.publisher,
    )

    dto = use_case.execute(
        StartPublishRequestDTO(
            media_asset_id=media.id,
            title="B upload",
            channel_id=channel_b.id,
        ),
        async_upload=False,
    )

    assert dto.channel_id == channel_b.id
    assert dto.platform_connection_id == dto_b.id
    assert len(stack.publisher.uploads) == 1
    assert stack.publisher.uploads[0]["access_token"] == "access-b"
    saved = publish_repo.get_by_id(dto.id)
    assert saved.channel_attribution == "exact"
    assert saved.status == PublishStatus.PUBLISHED


def test_scheduled_publishes_remain_independent_per_channel(tmp_path):
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    channel_a = stack.channels.get_by_id(dto_a.channels[0].id)
    channel_b = stack.channels.get_by_id(dto_b.channels[0].id)
    media_repo = FakeMediaRepo()
    media = add_media(media_repo, tmp_path)
    publish_repo = FakePublishRepo()
    schedule_repo = FakeScheduleRepo()
    create_use_case = CreateScheduledPublishUseCase(
        schedule_repo=schedule_repo,
        media_repo=media_repo,
        resolver=stack.resolver,
        publish_repo=publish_repo,
    )
    future = "2026-11-06T10:00:00+00:00"

    sched_a = create_use_case.execute(
        CreateScheduledPublishDTO(
            media_asset_id=media.id,
            title="Channel A plan",
            scheduled_at_iso=future,
            timezone="UTC",
            channel_id=channel_a.id,
        )
    )
    sched_b = create_use_case.execute(
        CreateScheduledPublishDTO(
            media_asset_id=media.id,
            title="Channel B plan",
            scheduled_at_iso=future,
            timezone="UTC",
            channel_id=channel_b.id,
        )
    )

    stored_a = schedule_repo.get_by_id(sched_a.id)
    stored_b = schedule_repo.get_by_id(sched_b.id)
    assert stored_a.channel_id == channel_a.id
    assert stored_a.platform_connection_id == dto_a.id
    assert stored_a.channel_attribution == "exact"
    assert stored_b.channel_id == channel_b.id
    assert stored_b.platform_connection_id == dto_b.id
    assert stored_b.channel_attribution == "exact"

    now = datetime.now(timezone.utc)
    stored_a.scheduled_at_utc = now - timedelta(minutes=2)
    stored_b.scheduled_at_utc = now - timedelta(minutes=1)

    publish_use_case = PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=FakeStorage(),
        resolver=stack.resolver,
        access_provider=stack.access,
        publish_repo=publish_repo,
        publisher=stack.publisher,
    )
    scheduler = ProcessDueScheduledPublishesUseCase(
        schedule_repo=schedule_repo,
        publish_repo=publish_repo,
        publish_use_case=publish_use_case,
    )

    assert scheduler.execute() == 2

    assert [upload["access_token"] for upload in stack.publisher.uploads] == [
        "access-a",
        "access-b",
    ]
    final_a = schedule_repo.get_by_id(sched_a.id)
    final_b = schedule_repo.get_by_id(sched_b.id)
    assert final_a.status == ScheduleStatus.PUBLISHED
    assert final_b.status == ScheduleStatus.PUBLISHED

    pub_a = publish_repo.get_by_id(final_a.publish_record_id)
    pub_b = publish_repo.get_by_id(final_b.publish_record_id)
    assert pub_a.channel_id == channel_a.id
    assert pub_a.platform_connection_id == dto_a.id
    assert pub_b.channel_id == channel_b.id
    assert pub_b.platform_connection_id == dto_b.id
    assert final_a.publish_record_id != final_b.publish_record_id


def test_scheduler_refuses_unresolved_channel(tmp_path):
    stack = build_stack()
    dto_a, _ = connect_two_accounts(stack)
    channel_a = stack.channels.get_by_id(dto_a.channels[0].id)
    media_repo = FakeMediaRepo()
    media = add_media(media_repo, tmp_path)
    publish_repo = FakePublishRepo()
    schedule_repo = FakeScheduleRepo()
    publish_use_case = PublishVideoToYouTubeUseCase(
        media_repo=media_repo,
        storage=FakeStorage(),
        resolver=stack.resolver,
        access_provider=stack.access,
        publish_repo=publish_repo,
        publisher=stack.publisher,
    )
    scheduler = ProcessDueScheduledPublishesUseCase(
        schedule_repo=schedule_repo,
        publish_repo=publish_repo,
        publish_use_case=publish_use_case,
    )

    unresolved = ScheduledPublish(
        id="sched_unresolved",
        media_asset_id=media.id,
        title="legacy row",
        scheduled_at_utc=datetime.now(timezone.utc) - timedelta(minutes=5),
        channel_id=None,
        platform_connection_id=None,
        channel_attribution="unresolved",
        status=ScheduleStatus.SCHEDULED,
    )
    schedule_repo.save(unresolved)

    processed = scheduler.execute()

    assert processed == 1
    stored = schedule_repo.get_by_id(unresolved.id)
    assert stored.status == ScheduleStatus.FAILED
    assert stored.last_error_code == "CHANNEL_UNRESOLVED"
    assert stored.channel_id is None
    assert stack.publisher.uploads == []
    assert publish_repo.count() == 0
    # The resolved channel was never touched by the unresolved job.
    assert stack.channels.get_by_id(channel_a.id).id == channel_a.id


def test_one_expired_token_does_not_break_other_connection():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    conn_a = stack.connections.get_by_id(dto_a.id)
    conn_b = stack.connections.get_by_id(dto_b.id)
    conn_a.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

    access_a = stack.access.get_access(stack.resolver.resolve(dto_a.channels[0].id))
    assert access_a.access_token == "refreshed::refresh-a"
    assert stack.publisher.refresh_log == ["refresh-a"]
    assert conn_a.is_token_expired() is False
    assert stack.tokens.get_access_token(conn_a.token_reference) == "refreshed::refresh-a"
    assert stack.tokens.get_access_token(conn_b.token_reference) == "access-b"

    stack.tokens.delete_tokens(conn_a.token_reference)
    conn_a.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    with pytest.raises(AuthenticationRequiredException):
        stack.access.get_access(stack.resolver.resolve(dto_a.channels[0].id))
    assert conn_a.connection_status == ConnectionStatus.REAUTH_REQUIRED

    # B keeps working while A needs re-authentication.
    access_b = stack.access.get_access(stack.resolver.resolve(dto_b.channels[0].id))
    assert access_b.access_token == "access-b"
    assert conn_b.connection_status == ConnectionStatus.ACTIVE


def test_disconnect_affects_only_the_target_connection(tmp_path):
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    channel_a = stack.channels.get_by_id(dto_a.channels[0].id)
    channel_b = stack.channels.get_by_id(dto_b.channels[0].id)
    conn_a = stack.connections.get_by_id(dto_a.id)

    media_repo = FakeMediaRepo()
    media = add_media(media_repo, tmp_path)
    publish_repo = FakePublishRepo()
    schedule_repo = FakeScheduleRepo()
    pub_a = publish_repo.save(pending_publish(channel_a, media.id))
    pub_b = publish_repo.save(pending_publish(channel_b, media.id))
    sched_a = schedule_repo.save(
        pending_schedule(channel_a, media.id, datetime.now(timezone.utc) + timedelta(hours=1))
    )
    sched_b = schedule_repo.save(
        pending_schedule(channel_b, media.id, datetime.now(timezone.utc) + timedelta(hours=1))
    )
    stack.resolver.select(channel_a.id)

    use_case = DisconnectPlatformConnectionUseCase(
        connection_repo=stack.connections,
        channel_repo=stack.channels,
        selection_repo=stack.selection,
        publish_repo=publish_repo,
        schedule_repo=schedule_repo,
        token_storage=stack.tokens,
    )
    assert use_case.execute(conn_a.id) is True

    assert conn_a.connection_status == ConnectionStatus.DISCONNECTED
    assert stack.tokens.get_access_token(conn_a.token_reference) is None
    assert channel_a.is_enabled is False
    assert publish_repo.get_by_id(pub_a.id).status == PublishStatus.FAILED
    assert publish_repo.get_by_id(pub_a.id).error_code == "CONNECTION_DISCONNECTED"
    assert schedule_repo.get_by_id(sched_a.id).status == ScheduleStatus.FAILED

    assert channel_b.is_enabled is True
    assert publish_repo.get_by_id(pub_b.id).status == PublishStatus.PENDING
    assert schedule_repo.get_by_id(sched_b.id).status == ScheduleStatus.SCHEDULED
    conn_b = stack.connections.get_by_id(dto_b.id)
    assert conn_b.is_active is True
    assert stack.tokens.get_access_token(conn_b.token_reference) == "access-b"
    # Selection must move to the still-usable connection.
    assert stack.selection.get().active_channel_id == channel_b.id


def test_duplicate_oauth_callback_does_not_create_duplicate_connection():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Channel A1")],
    )
    state, _ = oauth_session_store.create_session()
    first = stack.complete.execute("code-a", state)
    assert stack.connections.count() == 1

    with pytest.raises(DuplicateOAuthCallbackException):
        stack.complete.execute("code-a", state)

    assert stack.connections.count() == 1
    assert stack.channels.count(enabled_only=False) == 1
    assert stack.connections.get_by_id(first.id) is not None


def test_readding_same_google_account_updates_without_duplicate():
    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a1",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Channel A1")],
    )
    first = stack.connect("code-a1")

    register_account(
        stack.publisher,
        "code-a2",
        "access-a2",
        "refresh-a2",
        "google-sub-a",
        "Account A Renamed",
        [profile("UC_A1", "Channel A1 Renamed")],
    )
    second = stack.connect("code-a2")

    assert stack.connections.count() == 1
    assert second.id == first.id
    assert stack.channels.count(enabled_only=False) == 1
    channel = stack.channels.get_by_id(first.channels[0].id)
    assert channel.channel_name == "Channel A1 Renamed"
    assert stack.tokens.get_access_token(
        stack.connections.get_by_id(first.id).token_reference
    ) == "access-a2"


def test_inaccessible_channels_are_denied():
    stack = build_stack()
    dto_a, dto_b = connect_two_accounts(stack)
    channel_a = stack.channels.get_by_id(dto_a.channels[0].id)
    channel_b = stack.channels.get_by_id(dto_b.channels[0].id)

    with pytest.raises(ChannelNotFoundException):
        stack.resolver.resolve("does-not-exist")

    stack.channels.set_enabled(channel_a.id, False)
    with pytest.raises(ChannelDisabledException):
        stack.resolver.resolve(channel_a.id)

    conn_b = stack.connections.get_by_id(dto_b.id)
    conn_b.disconnect()
    stack.connections.save(conn_b)
    with pytest.raises(ConnectionInactiveException):
        stack.resolver.resolve(channel_b.id)
    with pytest.raises(ConnectionInactiveException):
        stack.access.get_access(
            ChannelContext(channel=channel_b, connection=conn_b)
        )

    enabled_external_ids = {
        context.external_channel_id for context in stack.resolver.list_contexts()
    }
    assert enabled_external_ids == set()
    all_external_ids = {
        context.external_channel_id
        for context in stack.resolver.list_contexts(
            include_disabled=True, include_disconnected=True
        )
    }
    assert {"UC_A1", "UC_B1"} <= all_external_ids


def test_frontend_selector_persistence_contract():
    context_src = (REPO_ROOT / "frontend/src/context/ChannelContext.tsx").read_text()
    api_src = (REPO_ROOT / "frontend/src/services/api.ts").read_text()
    accounts_src = (REPO_ROOT / "frontend/src/pages/ConnectedAccountsPage.tsx").read_text()
    publish_types = (REPO_ROOT / "frontend/src/types/publish.ts").read_text()
    modal_src = (REPO_ROOT / "frontend/src/components/youtube/YouTubePublishModal.tsx").read_text()

    # Server-side selection is authoritative; localStorage is only a mirror.
    assert "tezlify.active_channel_id" in context_src
    assert "channelsRes.selection" in context_src
    assert "apiService.selectChannel" in context_src
    assert "getChannelSelection" in api_src
    assert "selectChannel(channelId" in api_src

    # Every channel-scoped API call carries channel_id.
    assert "function withChannel" in api_src
    assert "channel_id" in publish_types
    assert "channel_id: channelId" in modal_src
    assert "connectYouTube('add_account')" in accounts_src


def test_connections_endpoint_serializes_channel_dtos():
    from tezlify_studio.presentation.api.routes.accounts import list_connections

    stack = build_stack()
    register_account(
        stack.publisher,
        "code-a",
        "access-a",
        "refresh-a",
        "google-sub-a",
        "Account A",
        [profile("UC_A1", "Channel A1")],
    )
    dto = stack.connect("code-a")

    class _UseCase:
        def execute(self, include_disconnected: bool = False):
            return [dto]

    response = list_connections(include_disconnected=False, use_case=_UseCase())

    assert response.total == 1
    assert response.items[0].channel_count == 1
    assert response.items[0].channels[0].channel_external_id == "UC_A1"
    assert response.items[0].channels[0].channel_name == "Channel A1"


def test_platform_capabilities_only_advertise_implemented_platforms():
    platforms = {item.id: item for item in ListPlatformsUseCase(PlatformCatalog()).execute()}

    assert set(platforms) == {"youtube", "instagram", "tiktok"}
    assert platforms["youtube"].implemented is True
    assert platforms["youtube"].capabilities["upload_video"] is True
    assert platforms["youtube"].capabilities["schedule_publish"] is True
    assert platforms["youtube"].capabilities["monetization_revenue"] is False

    for platform_id in ("instagram", "tiktok"):
        descriptor = platforms[platform_id]
        assert descriptor.implemented is False
        assert descriptor.capabilities
        assert not any(descriptor.capabilities.values())


# ---------------------------------------------------------------------------
# §4 migration on throw-away SQLite databases
# ---------------------------------------------------------------------------
def _run_alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["PYTHONPATH"] = os.path.abspath("backend/src")
    env["TEZLIFY_MIGRATION_BACKUP_DIR"] = str(db_path.parent / "backups")
    result = subprocess.run(
        [os.path.abspath(".venv/bin/alembic"), *args],
        cwd="backend",
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{' '.join(args)} failed:\n{result.stderr}\n{result.stdout}"
    return result


def _seed_legacy_database(db_path: Path, accounts: int = 1) -> None:
    _run_alembic(db_path, "upgrade", "c92f45a1d7b0")
    con = sqlite3.connect(db_path)
    now = "2026-11-01 10:00:00.000000"
    for index in range(3):
        con.execute(
            "INSERT INTO media_assets (id, filename, original_filename, file_path, "
            "file_size_bytes, mime_type, sha256_hash, status, thumbnail_path, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, 10, 'video/mp4', ?, 'ready', "
            "NULL, ?, ?)",
            (
                f"media-legacy-{index}",
                f"legacy_{index}.mp4",
                f"legacy_{index}.mp4",
                f"/tmp/legacy_{index}.mp4",
                f"hash-legacy-{index}",
                now,
                now,
            ),
        )
    for index in range(accounts):
        con.execute(
            "INSERT INTO social_accounts (id, platform, account_name, channel_id, "
            "channel_avatar_url, is_active, token_expires_at, created_at, updated_at) "
            "VALUES (?, 'youtube', ?, ?, NULL, 1, NULL, ?, ?)",
            (f"legacy-acc-{index}", f"Legacy Channel {index}", f"UC_LEGACY_{index}", now, now),
        )
    for index in range(3):
        con.execute(
            "INSERT INTO publish_records (id, media_asset_id, platform, external_video_id, "
            "external_video_url, title, description, tags_json, category_id, privacy_status, "
            "status, progress_percentage, uploaded_bytes, total_bytes, upload_session_uri, "
            "thumbnail_path, error_code, error_message, created_at, updated_at, published_at) "
            "VALUES (?, ?, 'youtube', NULL, NULL, ?, '', '[]', '22', 'private', 'published', "
            "100, 10, 10, NULL, NULL, NULL, NULL, ?, ?, NULL)",
            (f"pub-legacy-{index}", f"media-legacy-{index}", f"Legacy video {index}", now, now),
        )
    for index in range(2):
        con.execute(
            "INSERT INTO scheduled_publishes (id, media_asset_id, social_account_id, platform, "
            "title, description, tags_json, privacy_status, scheduled_at_utc, timezone, status, "
            "publish_record_id, attempt_count, max_attempts, last_error_code, last_error_message, "
            "started_at, completed_at, created_at, updated_at, version) "
            "VALUES (?, ?, 'legacy-acc-0', 'youtube', ?, '', '[]', 'private', ?, 'UTC', "
            "'scheduled', NULL, 0, 3, NULL, NULL, NULL, NULL, ?, ?, 1)",
            (
                f"sched-legacy-{index}",
                f"media-legacy-{index}",
                f"Legacy schedule {index}",
                now,
                now,
                now,
            ),
        )
    con.commit()
    con.close()


def _read_records(db_path: Path, query: str) -> List[sqlite3.Row]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def test_migration_maps_legacy_single_account_and_preserves_records(tmp_path):
    db_path = tmp_path / "legacy_single.db"
    _seed_legacy_database(db_path, accounts=1)
    _run_alembic(db_path, "upgrade", "head")

    connections = _read_records(
        db_path,
        "SELECT id, platform, account_external_id, account_display_name, connection_status, "
        "token_reference FROM platform_connections",
    )
    assert len(connections) == 1
    connection = connections[0]
    assert connection["id"] == "legacy-acc-0"
    assert connection["token_reference"] == "legacy-acc-0"
    assert connection["account_external_id"] == "legacy:UC_LEGACY_0"
    assert connection["connection_status"] == "active"

    channels = _read_records(
        db_path,
        "SELECT id, platform_connection_id, channel_external_id, channel_name, is_primary, "
        "is_enabled FROM platform_channels",
    )
    assert len(channels) == 1
    channel = channels[0]
    assert channel["platform_connection_id"] == connection["id"]
    assert channel["channel_external_id"] == "UC_LEGACY_0"
    assert channel["is_primary"] == 1
    assert channel["is_enabled"] == 1

    publishes = _read_records(
        db_path,
        "SELECT id, channel_id, platform_connection_id, channel_attribution "
        "FROM publish_records ORDER BY id",
    )
    assert len(publishes) == 3
    assert [row["id"] for row in publishes] == [
        "pub-legacy-0",
        "pub-legacy-1",
        "pub-legacy-2",
    ]
    for row in publishes:
        assert row["channel_id"] == channel["id"]
        assert row["platform_connection_id"] == connection["id"]
        assert row["channel_attribution"] == "legacy_single_account"

    schedules = _read_records(
        db_path,
        "SELECT id, channel_id, platform_connection_id, channel_attribution, "
        "social_account_id FROM scheduled_publishes ORDER BY id",
    )
    assert len(schedules) == 2
    for row in schedules:
        assert row["social_account_id"] == "legacy-acc-0"
        assert row["channel_id"] == channel["id"]
        assert row["platform_connection_id"] == connection["id"]
        assert row["channel_attribution"] == "legacy_social_account"

    preferences = _read_records(
        db_path, "SELECT active_channel_id, default_platform FROM user_channel_preferences"
    )
    assert preferences[0]["active_channel_id"] == channel["id"]
    assert preferences[0]["default_platform"] == "youtube"

    # Old tables and every row still exist: the migration is additive.
    assert _read_records(db_path, "SELECT COUNT(*) AS c FROM social_accounts")[0]["c"] == 1
    assert _read_records(db_path, "SELECT COUNT(*) AS c FROM publish_records")[0]["c"] == 3
    assert (
        _read_records(db_path, "SELECT COUNT(*) AS c FROM scheduled_publishes")[0]["c"] == 2
    )
    assert _read_records(db_path, "PRAGMA foreign_key_check") == []

    # No plaintext OAuth token columns were introduced.
    connection_columns = {
        row["name"] for row in _read_records(db_path, "PRAGMA table_info(platform_connections)")
    }
    assert "access_token" not in connection_columns
    assert "refresh_token" not in connection_columns

    # A valid backup was written before DDL.
    backups = sorted((tmp_path / "backups").glob("*.db"))
    assert backups, "migration must create a backup before changing the schema"
    backup = _read_records(backups[0], "SELECT COUNT(*) AS c FROM social_accounts")
    assert backup[0]["c"] == 1
    assert _read_records(backups[0], "PRAGMA integrity_check")[0][0] == "ok"


def test_migration_keeps_ambiguous_publish_attribution_unresolved(tmp_path):
    db_path = tmp_path / "legacy_ambiguous.db"
    _seed_legacy_database(db_path, accounts=2)
    _run_alembic(db_path, "upgrade", "head")

    assert (
        _read_records(db_path, "SELECT COUNT(*) AS c FROM platform_connections")[0]["c"] == 2
    )
    assert _read_records(db_path, "SELECT COUNT(*) AS c FROM platform_channels")[0]["c"] == 2

    publishes = _read_records(
        db_path,
        "SELECT channel_id, platform_connection_id, channel_attribution FROM publish_records",
    )
    assert len(publishes) == 3
    for row in publishes:
        # With two possible channels there is no proof of ownership: never guess.
        assert row["channel_id"] is None
        assert row["platform_connection_id"] is None
        assert row["channel_attribution"] == "unresolved"

    assert _read_records(db_path, "PRAGMA foreign_key_check") == []
    assert _read_records(db_path, "SELECT COUNT(*) AS c FROM social_accounts")[0]["c"] == 2
    assert _read_records(db_path, "SELECT COUNT(*) AS c FROM publish_records")[0]["c"] == 3


@pytest.mark.parametrize("dummy", [0])
def test_migration_never_loses_legacy_rows(dummy, tmp_path):
    """Both seeds must round-trip every legacy row into the new schema."""
    for accounts in (1, 2):
        db_path = tmp_path / f"lossless_{accounts}.db"
        _seed_legacy_database(db_path, accounts=accounts)
        _run_alembic(db_path, "upgrade", "head")

        assert (
            _read_records(db_path, "SELECT COUNT(*) AS c FROM social_accounts")[0]["c"]
            == accounts
        )
        assert (
            _read_records(db_path, "SELECT COUNT(*) AS c FROM platform_connections")[0]["c"]
            == accounts
        )
        assert (
            _read_records(db_path, "SELECT COUNT(*) AS c FROM platform_channels")[0]["c"]
            == accounts
        )
        assert _read_records(db_path, "SELECT COUNT(*) AS c FROM publish_records")[0]["c"] == 3
        assert (
            _read_records(db_path, "SELECT COUNT(*) AS c FROM scheduled_publishes")[0]["c"]
            == 2
        )
