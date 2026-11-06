"""Playlist and thumbnail API contract tests.

Every YouTube port is a fake, so nothing is sent to a real channel.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from tezlify_studio.application.ports.creator_gateway_port import CreatorSession
from tezlify_studio.application.services.youtube_capability_service import (
    YouTubeCapabilityService,
)
from tezlify_studio.application.use_cases.add_video_to_playlist_use_case import (
    AddVideoToPlaylistUseCase,
)
from tezlify_studio.application.use_cases.create_playlist_use_case import (
    CreatePlaylistUseCase,
)
from tezlify_studio.application.use_cases.delete_channel_video_use_case import (
    DeleteChannelVideoUseCase,
)
from tezlify_studio.application.use_cases.delete_playlist_use_case import (
    DeletePlaylistUseCase,
)
from tezlify_studio.application.use_cases.move_playlist_item_use_case import (
    MovePlaylistItemUseCase,
)
from tezlify_studio.application.use_cases.list_playlist_items_use_case import (
    ListPlaylistItemsUseCase,
)
from tezlify_studio.application.use_cases.remove_video_from_playlist_use_case import (
    RemoveVideoFromPlaylistUseCase,
)
from tezlify_studio.application.use_cases.set_video_thumbnail_use_case import (
    SetVideoThumbnailUseCase,
)
from tezlify_studio.application.use_cases.update_playlist_use_case import (
    UpdatePlaylistUseCase,
)
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext
from tezlify_studio.domain.value_objects.creator_models import (
    ChannelPlaylist,
    PlaylistItem,
)
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    SCOPE_COMMENTS,
    SCOPE_UPLOAD,
)
from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies import container

SCOPE_CHANNEL_READ = "https://www.googleapis.com/auth/youtube.readonly"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32


class FakeChannelPort:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []
        self.added: List[tuple] = []
        self.removed: List[tuple] = []
        self.thumbnails: List[tuple] = []
        self.updated: List[Dict[str, Any]] = []
        self.deleted_playlists: List[str] = []
        self.moved: List[tuple] = []
        self.deleted_videos: List[str] = []

    def list_playlist_items(self, playlist_id: str, max_results: int = 50) -> List[PlaylistItem]:
        return [
            PlaylistItem(
                playlist_item_id="pli1",
                playlist_id=playlist_id,
                video_id="v1",
                title="Bölüm 1",
                position=0,
            )
        ]

    def create_playlist(self, title: str, description: str = "", privacy: str = "private") -> ChannelPlaylist:
        self.created.append(
            {"title": title, "description": description, "privacy": privacy}
        )
        return ChannelPlaylist(
            playlist_id="pl_new",
            title=title,
            description=description,
            item_count=0,
        )

    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> PlaylistItem:
        self.added.append((playlist_id, video_id))
        return PlaylistItem(
            playlist_item_id="pli_new",
            playlist_id=playlist_id,
            video_id=video_id,
            title="Bölüm 1",
        )

    def remove_video_from_playlist(self, playlist_id: str, video_id: str) -> bool:
        self.removed.append((playlist_id, video_id))
        return video_id != "missing_video"

    def set_video_thumbnail(self, video_id: str, image_bytes: bytes, content_type: str) -> bool:
        self.thumbnails.append((video_id, len(image_bytes), content_type))
        return True

    def update_playlist(
        self,
        playlist_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        privacy: Optional[str] = None,
    ) -> ChannelPlaylist:
        self.updated.append(
            {
                "playlist_id": playlist_id,
                "title": title,
                "description": description,
                "privacy": privacy,
            }
        )
        return ChannelPlaylist(
            playlist_id=playlist_id,
            title=title or "Liste",
            description=description or "",
            privacy_status=privacy,
        )

    def delete_playlist(self, playlist_id: str) -> bool:
        self.deleted_playlists.append(playlist_id)
        return True

    def move_playlist_item(self, playlist_id: str, video_id: str, position: int) -> bool:
        self.moved.append((playlist_id, video_id, position))
        return video_id != "missing_video"

    def delete_video(self, video_id: str) -> bool:
        self.deleted_videos.append(video_id)
        return True


class FakeResolver:
    def __init__(self, scopes: Optional[List[str]] = None) -> None:
        self.scopes = list(scopes if scopes is not None else [SCOPE_CHANNEL_READ])

    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        return ChannelContext(
            channel=PlatformChannel(
                id="local_ch_1",
                platform_connection_id="conn_1",
                platform=SocialPlatform.YOUTUBE,
                channel_external_id="UC_FAKE",
                channel_name="Test Kanalı",
            ),
            connection=PlatformConnection(
                id="conn_1",
                platform=SocialPlatform.YOUTUBE,
                account_external_id="google_1",
                account_display_name="Test Hesabı",
                granted_scopes=self.scopes,
            ),
        )


class FakeGateway:
    def __init__(self, channel: FakeChannelPort) -> None:
        self.channel = channel

    def bind(self, context: ChannelContext) -> CreatorSession:
        return CreatorSession(
            channel=self.channel,
            analytics=None,
            comments=None,
            access=ChannelAccess(
                platform=SocialPlatform.YOUTUBE,
                channel_id=context.channel_id,
                external_channel_id=context.external_channel_id,
                connection_id=context.connection_id,
                access_token="mock_access_token",
            ),
        )


@pytest.fixture()
def channel_port() -> FakeChannelPort:
    return FakeChannelPort()


@pytest.fixture()
def resolver() -> FakeResolver:
    return FakeResolver()


def _build_client(channel: FakeChannelPort, resolver: FakeResolver) -> TestClient:
    gateway = FakeGateway(channel)
    capabilities = YouTubeCapabilityService()
    overrides = {
        container.get_list_playlist_items_use_case: lambda: ListPlaylistItemsUseCase(
            resolver, gateway
        ),
        container.get_create_playlist_use_case: lambda: CreatePlaylistUseCase(
            resolver, gateway, capabilities
        ),
        container.get_add_video_to_playlist_use_case: lambda: AddVideoToPlaylistUseCase(
            resolver, gateway, capabilities
        ),
        container.get_remove_video_from_playlist_use_case: lambda: RemoveVideoFromPlaylistUseCase(
            resolver, gateway, capabilities
        ),
        container.get_set_video_thumbnail_use_case: lambda: SetVideoThumbnailUseCase(
            resolver, gateway, capabilities
        ),
        container.get_update_playlist_use_case: lambda: UpdatePlaylistUseCase(
            resolver, gateway, capabilities
        ),
        container.get_delete_playlist_use_case: lambda: DeletePlaylistUseCase(
            resolver, gateway, capabilities
        ),
        container.get_move_playlist_item_use_case: lambda: MovePlaylistItemUseCase(
            resolver, gateway, capabilities
        ),
        container.get_delete_channel_video_use_case: lambda: DeleteChannelVideoUseCase(
            resolver, gateway, capabilities
        ),
    }
    app.dependency_overrides.update(overrides)
    return TestClient(app)


@pytest.fixture()
def client(channel_port: FakeChannelPort, resolver: FakeResolver) -> TestClient:
    client = _build_client(channel_port, resolver)
    yield client
    app.dependency_overrides.clear()


def test_list_playlist_items_returns_positions(
    client: TestClient, channel_port: FakeChannelPort
) -> None:
    response = client.get("/api/v1/channels/youtube/playlists/pl1/items")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["video_id"] == "v1"
    assert body["items"][0]["position"] == 0
    assert body["source"] == "youtube_data_api"


def test_create_playlist_requires_write_scope(
    client: TestClient, channel_port: FakeChannelPort
) -> None:
    payload = {"title": "Seri", "description": "Açıklama", "privacy_status": "unlisted"}

    denied = client.post("/api/v1/channels/youtube/playlists", json=payload)
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "INSUFFICIENT_SCOPE"
    assert channel_port.created == []


def test_create_playlist_validates_and_forwards_values(
    channel_port: FakeChannelPort, resolver: FakeResolver
) -> None:
    resolver.scopes = [SCOPE_CHANNEL_READ, SCOPE_COMMENTS]
    client = _build_client(channel_port, resolver)
    try:
        blank = client.post(
            "/api/v1/channels/youtube/playlists", json={"title": "   "}
        )
        assert blank.status_code == 400

        bad_privacy = client.post(
            "/api/v1/channels/youtube/playlists",
            json={"title": "Seri", "privacy_status": "secret"},
        )
        assert bad_privacy.status_code == 422

        created = client.post(
            "/api/v1/channels/youtube/playlists",
            json={"title": "  Seri  ", "description": "Açıklama", "privacy_status": "unlisted"},
        )
        assert created.status_code == 201
        assert created.json()["playlist"]["playlist_id"] == "pl_new"
        assert channel_port.created == [
            {"title": "Seri", "description": "Açıklama", "privacy": "unlisted"}
        ]
    finally:
        app.dependency_overrides.clear()


def test_add_and_remove_playlist_items(
    channel_port: FakeChannelPort, resolver: FakeResolver
) -> None:
    resolver.scopes = [SCOPE_CHANNEL_READ, SCOPE_COMMENTS]
    client = _build_client(channel_port, resolver)
    try:
        added = client.post(
            "/api/v1/channels/youtube/playlists/pl1/items", json={"video_id": "v1"}
        )
        assert added.status_code == 201
        assert added.json()["item"]["video_id"] == "v1"
        assert channel_port.added == [("pl1", "v1")]

        removed = client.delete("/api/v1/channels/youtube/playlists/pl1/items/v1")
        assert removed.status_code == 200
        assert removed.json()["success"] is True
        assert channel_port.removed == [("pl1", "v1")]

        missing = client.delete("/api/v1/channels/youtube/playlists/pl1/items/missing_video")
        assert missing.status_code == 200
        assert missing.json()["success"] is False
    finally:
        app.dependency_overrides.clear()


def test_playlist_write_is_denied_without_scope(
    client: TestClient, channel_port: FakeChannelPort
) -> None:
    add = client.post(
        "/api/v1/channels/youtube/playlists/pl1/items", json={"video_id": "v1"}
    )
    assert add.status_code == 403
    assert channel_port.added == []

    remove = client.delete("/api/v1/channels/youtube/playlists/pl1/items/v1")
    assert remove.status_code == 403
    assert channel_port.removed == []


def test_thumbnail_upload_validates_bytes_and_scope(
    channel_port: FakeChannelPort, resolver: FakeResolver
) -> None:
    resolver.scopes = [SCOPE_CHANNEL_READ, SCOPE_UPLOAD]
    client = _build_client(channel_port, resolver)
    try:
        ok = client.post(
            "/api/v1/channels/youtube/videos/v1/thumbnail",
            files={"file": ("cover.png", PNG_BYTES, "image/png")},
        )
        assert ok.status_code == 200
        assert ok.json()["updated"] is True
        assert channel_port.thumbnails == [("v1", len(PNG_BYTES), "image/png")]

        jpeg = client.post(
            "/api/v1/channels/youtube/videos/v1/thumbnail",
            files={"file": ("cover.jpg", JPEG_BYTES, "image/jpeg")},
        )
        assert jpeg.status_code == 200

        bad_type = client.post(
            "/api/v1/channels/youtube/videos/v1/thumbnail",
            files={"file": ("cover.gif", b"GIF89a", "image/gif")},
        )
        assert bad_type.status_code == 400

        bad_signature = client.post(
            "/api/v1/channels/youtube/videos/v1/thumbnail",
            files={"file": ("cover.png", b"not-a-png-file", "image/png")},
        )
        assert bad_signature.status_code == 400

        oversize = client.post(
            "/api/v1/channels/youtube/videos/v1/thumbnail",
            files={"file": ("cover.png", PNG_BYTES + b"0" * (2 * 1024 * 1024), "image/png")},
        )
        assert oversize.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_thumbnail_requires_upload_scope(
    client: TestClient, channel_port: FakeChannelPort
) -> None:
    response = client.post(
        "/api/v1/channels/youtube/videos/v1/thumbnail",
        files={"file": ("cover.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "INSUFFICIENT_SCOPE"
    assert channel_port.thumbnails == []


def test_update_playlist_validates_and_forwards_changes(
    channel_port: FakeChannelPort, resolver: FakeResolver
) -> None:
    resolver.scopes = [SCOPE_CHANNEL_READ, SCOPE_COMMENTS]
    client = _build_client(channel_port, resolver)
    try:
        updated = client.patch(
            "/api/v1/channels/youtube/playlists/pl1",
            json={"title": "  Yeni Ad  ", "privacy_status": "unlisted"},
        )
        assert updated.status_code == 200
        assert updated.json()["playlist"]["title"] == "Yeni Ad"
        assert channel_port.updated == [
            {
                "playlist_id": "pl1",
                "title": "Yeni Ad",
                "description": None,
                "privacy": "unlisted",
            }
        ]

        blank = client.patch(
            "/api/v1/channels/youtube/playlists/pl1", json={"title": "   "}
        )
        assert blank.status_code == 400

        empty = client.patch("/api/v1/channels/youtube/playlists/pl1", json={})
        assert empty.status_code == 400

        bad_privacy = client.patch(
            "/api/v1/channels/youtube/playlists/pl1",
            json={"privacy_status": "secret"},
        )
        assert bad_privacy.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_delete_playlist_and_move_item(
    channel_port: FakeChannelPort, resolver: FakeResolver
) -> None:
    resolver.scopes = [SCOPE_CHANNEL_READ, SCOPE_COMMENTS]
    client = _build_client(channel_port, resolver)
    try:
        moved = client.patch(
            "/api/v1/channels/youtube/playlists/pl1/items/v1", json={"position": 2}
        )
        assert moved.status_code == 200
        assert moved.json()["position"] == 2
        assert channel_port.moved == [("pl1", "v1", 2)]

        missing = client.patch(
            "/api/v1/channels/youtube/playlists/pl1/items/missing_video",
            json={"position": 0},
        )
        assert missing.status_code == 404

        negative = client.patch(
            "/api/v1/channels/youtube/playlists/pl1/items/v1", json={"position": -1}
        )
        assert negative.status_code == 422

        deleted = client.delete("/api/v1/channels/youtube/playlists/pl1")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True
        assert channel_port.deleted_playlists == ["pl1"]
    finally:
        app.dependency_overrides.clear()


def test_playlist_update_and_delete_require_scope(
    client: TestClient, channel_port: FakeChannelPort
) -> None:
    update = client.patch(
        "/api/v1/channels/youtube/playlists/pl1", json={"title": "Yeni"}
    )
    assert update.status_code == 403
    assert update.json()["error_code"] == "INSUFFICIENT_SCOPE"
    assert channel_port.updated == []

    delete = client.delete("/api/v1/channels/youtube/playlists/pl1")
    assert delete.status_code == 403
    assert channel_port.deleted_playlists == []

    move = client.patch(
        "/api/v1/channels/youtube/playlists/pl1/items/v1", json={"position": 1}
    )
    assert move.status_code == 403
    assert channel_port.moved == []


def test_delete_video_forwards(
    channel_port: FakeChannelPort, resolver: FakeResolver
) -> None:
    resolver.scopes = [SCOPE_CHANNEL_READ, SCOPE_COMMENTS]
    client = _build_client(channel_port, resolver)
    try:
        deleted = client.delete("/api/v1/channels/youtube/videos/v1")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True
        assert channel_port.deleted_videos == ["v1"]
    finally:
        app.dependency_overrides.clear()


def test_delete_video_requires_scope(
    client: TestClient, channel_port: FakeChannelPort
) -> None:
    denied = client.delete("/api/v1/channels/youtube/videos/v1")
    assert denied.status_code == 403
    assert denied.json()["error_code"] == "INSUFFICIENT_SCOPE"
    assert channel_port.deleted_videos == []
