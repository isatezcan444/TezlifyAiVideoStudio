import io
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies.container import (
    get_youtube_publisher,
    get_token_storage,
)
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.infrastructure.security.token_storage_impl import InMemoryTokenStorageAdapter
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YOUTUBE_SCOPES
from tezlify_studio.infrastructure.media.youtube_api_client_impl import YouTubeApiClientImpl

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 64)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + (b"\x00" * 64)


class StudioFakePublisher(YouTubePublisherPort):
    def __init__(self):
        self.playlist_calls: List[Tuple[str, str]] = []
        self.thumbnail_calls: List[Tuple[str, str]] = []

    def generate_auth_url(
        self,
        state: str,
        code_challenge: str,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    def exchange_code_for_tokens(self, *args, **kwargs) -> Dict[str, Any]:
        return {
            "access_token": "studio_access_tok",
            "refresh_token": "studio_refresh_tok",
            "expires_in": 3600,
            "scope": " ".join(YOUTUBE_SCOPES),
        }

    def refresh_access_token(self, *args, **kwargs) -> Dict[str, Any]:
        return {"access_token": "studio_new_tok", "expires_in": 3600}

    def get_channel_profile(self, *args, **kwargs) -> Dict[str, Any]:
        return {"channel_id": "UC_STUDIO_TEST", "channel_title": "Studio Test Channel"}

    def initiate_resumable_upload(self, *args, **kwargs) -> str:
        return "https://upload.example.com/studio"

    def upload_chunk(self, *args, **kwargs):
        return 200, {"id": "yt_studio_vid"}

    def query_upload_status(self, *args, **kwargs) -> int:
        return 0

    def upload_custom_thumbnail(self, access_token: str, video_id: str, thumbnail_path: str) -> bool:
        self.thumbnail_calls.append((video_id, thumbnail_path))
        return True

    def add_video_to_playlist(self, access_token: str, playlist_id: str, video_id: str) -> bool:
        self.playlist_calls.append((playlist_id, video_id))
        return True


studio_publisher = StudioFakePublisher()
studio_token_storage = InMemoryTokenStorageAdapter()


@pytest.fixture(autouse=True)
def override_studio_deps():
    app.dependency_overrides[get_youtube_publisher] = lambda: studio_publisher
    app.dependency_overrides[get_token_storage] = lambda: studio_token_storage
    yield
    app.dependency_overrides.pop(get_youtube_publisher, None)
    app.dependency_overrides.pop(get_token_storage, None)


client = TestClient(app)


def create_sample_video() -> str:
    sample_bytes = b"ftypmp42" + uuid.uuid4().bytes + (b"\x00" * 300)
    files = {"file": ("studio_test_video.mp4", io.BytesIO(sample_bytes), "video/mp4")}
    res = client.post("/api/v1/media/upload", files=files)
    assert res.status_code == 201
    return res.json()["id"]


def connect_youtube_account() -> str:
    conn_res = client.post("/api/v1/social/youtube/connect")
    state = conn_res.json()["state"]
    client.get(f"/api/v1/social/youtube/callback?code=mock_code&state={state}")

    channels = client.get("/api/v1/channels").json()["items"]
    matching = [c for c in channels if c.get("channel_external_id") == "UC_STUDIO_TEST"]
    assert matching, "connected channel was not registered"
    channel_id = matching[-1]["id"]
    selection = client.put(
        "/api/v1/channels/selection", json={"channel_id": channel_id}
    )
    assert selection.status_code == 200
    return channel_id


def test_custom_thumbnail_upload_validates_and_replaces_previous_file():
    media_id = create_sample_video()

    first = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("cover.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["media_id"] == media_id
    assert first_data["thumbnail_path"].endswith(".png")
    assert first_data["file_size_bytes"] == len(PNG_BYTES)

    second = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("cover.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
    )
    assert second.status_code == 200
    second_path = second.json()["thumbnail_path"]
    assert second_path.endswith(".jpg")
    assert second_path != first_data["thumbnail_path"]
    assert not os.path.exists(first_data["thumbnail_path"])


def test_custom_thumbnail_rejects_unsupported_type_and_bad_signature():
    media_id = create_sample_video()

    gif = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("cover.gif", io.BytesIO(b"GIF89a" + b"\x00" * 32), "image/gif")},
    )
    assert gif.status_code == 400

    spoofed = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("cover.png", io.BytesIO(b"not-a-png"), "image/png")},
    )
    assert spoofed.status_code == 400


def test_custom_thumbnail_rejects_oversized_file():
    media_id = create_sample_video()
    oversized = PNG_BYTES + (b"\x00" * (2 * 1024 * 1024))
    res = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("big.png", io.BytesIO(oversized), "image/png")},
    )
    assert res.status_code == 400


def test_custom_thumbnail_unknown_media_returns_404():
    res = client.post(
        f"/api/v1/media/{uuid.uuid4()}/thumbnail",
        files={"file": ("cover.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert res.status_code == 404


def test_schedule_persists_playlist_thumbnail_and_category():
    channel_id = connect_youtube_account()
    media_id = create_sample_video()

    thumbnail = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("cover.png", io.BytesIO(PNG_BYTES), "image/png")},
    ).json()["thumbnail_path"]

    payload = {
        "media_asset_id": media_id,
        "channel_id": channel_id,
        "title": "Planlı Stüdyo Yayını",
        "description": "Oynatma listesi ve kapakla planlandı",
        "tags": ["studio", "plan"],
        "category_id": "28",
        "privacy_status": "unlisted",
        "thumbnail_path": thumbnail,
        "playlist_id": "PL_STUDIO_TEST",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "timezone": "Europe/Istanbul",
    }
    created = client.post("/api/v1/scheduler", json=payload)
    assert created.status_code == 201
    data = created.json()
    assert data["category_id"] == "28"
    assert data["privacy_status"] == "unlisted"
    assert data["thumbnail_path"] == thumbnail
    assert data["playlist_id"] == "PL_STUDIO_TEST"

    fetched = client.get(f"/api/v1/scheduler/{data['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["playlist_id"] == "PL_STUDIO_TEST"
    assert fetched.json()["category_id"] == "28"


def test_immediate_publish_persists_and_applies_playlist_and_thumbnail():
    channel_id = connect_youtube_account()
    media_id = create_sample_video()

    thumbnail = client.post(
        f"/api/v1/media/{media_id}/thumbnail",
        files={"file": ("cover.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
    ).json()["thumbnail_path"]

    studio_publisher.playlist_calls.clear()
    studio_publisher.thumbnail_calls.clear()

    res = client.post(
        "/api/v1/social/youtube/publish",
        json={
            "media_asset_id": media_id,
            "channel_id": channel_id,
            "title": "Stüdyo Yayını",
            "category_id": "28",
            "privacy_status": "private",
            "thumbnail_path": thumbnail,
            "playlist_id": "PL_STUDIO_TEST",
        },
    )
    assert res.status_code == 201
    publish_id = res.json()["id"]
    assert res.json()["playlist_id"] == "PL_STUDIO_TEST"
    assert res.json()["category_id"] == "28"
    assert res.json()["thumbnail_path"] == thumbnail

    deadline = time.time() + 10
    status = ""
    while time.time() < deadline:
        status = client.get(f"/api/v1/social/youtube/publish/{publish_id}").json()["status"]
        if status in ("published", "failed"):
            break
        time.sleep(0.1)

    assert status == "published"
    assert ("PL_STUDIO_TEST", "yt_studio_vid") in studio_publisher.playlist_calls
    assert ("yt_studio_vid", thumbnail) in studio_publisher.thumbnail_calls


def test_playlist_item_insert_posts_expected_payload():
    captured: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "PLITEM_1"})

    yt = YouTubeApiClientImpl(
        client_id="test_id",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert yt.add_video_to_playlist("tok_123", "PL_ABC", "VID_XYZ") is True
    assert "playlistItems" in captured["url"]
    assert captured["auth"] == "Bearer tok_123"
    assert captured["body"]["snippet"]["playlistId"] == "PL_ABC"
    assert captured["body"]["snippet"]["resourceId"] == {
        "kind": "youtube#video",
        "videoId": "VID_XYZ",
    }
