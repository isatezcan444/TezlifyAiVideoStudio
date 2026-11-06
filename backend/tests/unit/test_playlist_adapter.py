"""YouTube adapter tests for playlists and thumbnails.

All traffic goes through httpx.MockTransport; no real channel is touched.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelBindingMismatchException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
)
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.infrastructure.youtube.youtube_creator_api import YouTubeCreatorApi

CHANNEL_ACCESS = ChannelAccess(
    platform=SocialPlatform.YOUTUBE,
    channel_id="local_ch_1",
    external_channel_id="UC_REAL",
    connection_id="conn_1",
    access_token="mock_access_token",
)

CHANNEL = {
    "items": [
        {
            "id": "UC_REAL",
            "snippet": {"title": "Kanal", "description": ""},
            "statistics": {
                "subscriberCount": "1",
                "videoCount": "1",
                "viewCount": "1",
                "hiddenSubscriberCount": False,
            },
            "contentDetails": {"relatedPlaylists": {"uploads": "UU_REAL"}},
        }
    ]
}

PLAYLIST_ITEMS = {
    "items": [
        {
            "id": "pli_1",
            "snippet": {
                "title": "Bolum 1",
                "position": 0,
                "publishedAt": "2026-10-01T10:00:00Z",
                "resourceId": {"kind": "youtube#video", "videoId": "vid_1"},
                "thumbnails": {"medium": {"url": "https://img.example/med.jpg"}},
            },
            "contentDetails": {"videoId": "vid_1"},
        }
    ]
}


class Recorder:
    def __init__(self, playlist_owner: str = "UC_REAL", thumbnail_status: int = 200) -> None:
        self.requests: List[httpx.Request] = []
        self.playlist_owner = playlist_owner
        self.thumbnail_status = thumbnail_status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path

        if path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        if path.endswith("/thumbnails/set"):
            return httpx.Response(self.thumbnail_status, json={"kind": "youtube#thumbnailSetResponse"})
        if path.endswith("/playlists"):
            if request.method == "POST":
                body = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "id": "pl_new",
                        "snippet": body["snippet"],
                        "status": body["status"],
                    },
                )
            if request.method == "PUT":
                body = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "id": body["id"],
                        "snippet": body.get("snippet", {"title": "Liste"}),
                        "status": body.get("status", {"privacyStatus": "unlisted"}),
                    },
                )
            if request.method == "DELETE":
                return httpx.Response(204)
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": request.url.params.get("id"),
                            "snippet": {"channelId": self.playlist_owner, "title": "Liste"},
                        }
                    ]
                },
            )
        if path.endswith("/playlistItems"):
            if request.method == "POST":
                body = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "id": "pli_new",
                        "snippet": {
                            "title": "Bolum 1",
                            "position": 0,
                            "resourceId": body["snippet"]["resourceId"],
                        },
                    },
                )
            if request.method == "PUT":
                body = json.loads(request.content)
                return httpx.Response(200, json={"id": body["id"], "snippet": body["snippet"]})
            if request.method == "DELETE":
                return httpx.Response(204)
            if request.url.params.get("playlistId") == "UU_REAL":
                if request.url.params.get("videoId") == "vid_foreign":
                    return httpx.Response(200, json={"items": []})
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "pli_1",
                                "contentDetails": {"videoId": request.url.params.get("videoId")},
                            }
                        ]
                    },
                )
            if request.url.params.get("videoId"):
                return httpx.Response(
                    200,
                    json={"items": [{"id": "pli_1", "contentDetails": {"videoId": "vid_1"}}]},
                )
            return httpx.Response(200, json=PLAYLIST_ITEMS)
        if path.endswith("/videos") and request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"error": {"message": "unexpected"}})


def build_api(recorder: Recorder) -> YouTubeCreatorApi:
    client = httpx.Client(transport=httpx.MockTransport(recorder))
    return YouTubeCreatorApi(CHANNEL_ACCESS, client=client)


def test_list_playlist_items_checks_ownership_and_maps_fields() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    items = api.list_playlist_items("pl_1", max_results=200)

    assert [item.video_id for item in items] == ["vid_1"]
    assert items[0].playlist_item_id == "pli_1"
    assert items[0].thumbnail_url == "https://img.example/med.jpg"
    assert items[0].position == 0

    list_request = next(
        request for request in recorder.requests if request.url.path.endswith("/playlistItems")
    )
    assert list_request.url.params["maxResults"] == "50"


def test_list_playlist_items_rejects_foreign_playlist() -> None:
    api = build_api(Recorder(playlist_owner="UC_OTHER"))

    with pytest.raises(ChannelBindingMismatchException):
        api.list_playlist_items("pl_foreign")


def test_create_playlist_posts_snippet_and_status() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    playlist = api.create_playlist("Seri", "Aciklama", "unlisted")

    assert playlist.playlist_id == "pl_new"
    assert playlist.title == "Seri"
    post = next(
        request
        for request in recorder.requests
        if request.method == "POST" and request.url.path.endswith("/playlists")
    )
    body = json.loads(post.content)
    assert body == {
        "snippet": {"title": "Seri", "description": "Aciklama"},
        "status": {"privacyStatus": "unlisted"},
    }
    assert post.url.params["part"] == "snippet,status"


def test_add_video_to_playlist_verifies_both_ownerships() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    item = api.add_video_to_playlist("pl_1", "vid_1")

    assert item.video_id == "vid_1"
    assert item.playlist_item_id == "pli_new"
    post = next(
        request
        for request in recorder.requests
        if request.method == "POST" and request.url.path.endswith("/playlistItems")
    )
    body = json.loads(post.content)
    assert body["snippet"]["playlistId"] == "pl_1"
    assert body["snippet"]["resourceId"]["videoId"] == "vid_1"

    checked_video = any(
        request.url.params.get("videoId") == "vid_1"
        and request.url.params.get("playlistId") == "UU_REAL"
        for request in recorder.requests
    )
    assert checked_video is True


def test_remove_video_from_playlist_deletes_matching_item() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    assert api.remove_video_from_playlist("pl_1", "vid_1") is True

    delete_requests = [
        request for request in recorder.requests if request.method == "DELETE"
    ]
    assert len(delete_requests) == 1
    assert delete_requests[0].url.params["id"] == "pli_1"


def test_remove_video_returns_false_when_item_is_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        if request.url.path.endswith("/playlists"):
            return httpx.Response(
                200,
                json={"items": [{"id": "pl_1", "snippet": {"channelId": "UC_REAL"}}]},
            )
        return httpx.Response(200, json={"items": []})

    api = YouTubeCreatorApi(
        CHANNEL_ACCESS, client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    assert api.remove_video_from_playlist("pl_1", "vid_x") is False


def test_set_video_thumbnail_posts_image_bytes_and_content_type() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    assert api.set_video_thumbnail("vid_1", b"\x89PNG\r\n\x1a\nDATA", "image/png") is True

    upload = next(
        request for request in recorder.requests if request.url.path.endswith("/thumbnails/set")
    )
    assert upload.method == "POST"
    assert upload.url.params["videoId"] == "vid_1"
    assert upload.headers["Content-Type"] == "image/png"
    assert upload.content == b"\x89PNG\r\n\x1a\nDATA"


def test_set_video_thumbnail_401_requires_reauthentication() -> None:
    api = build_api(Recorder(thumbnail_status=401))

    with pytest.raises(AuthenticationRequiredException):
        api.set_video_thumbnail("vid_1", b"\x89PNG\r\n\x1a\nDATA", "image/png")


def test_list_playlists_maps_privacy_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "pl_1",
                        "snippet": {"title": "Liste", "description": ""},
                        "contentDetails": {"itemCount": 3},
                        "status": {"privacyStatus": "unlisted"},
                    }
                ]
            },
        )

    api = YouTubeCreatorApi(
        CHANNEL_ACCESS, client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    playlists = api.list_playlists()

    assert playlists[0].privacy_status == "unlisted"
    assert playlists[0].item_count == 3


def test_update_playlist_sends_only_requested_parts() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    playlist = api.update_playlist("pl_1", title="Yeni Ad", privacy="private")

    assert playlist.playlist_id == "pl_1"
    assert playlist.title == "Yeni Ad"
    assert playlist.privacy_status == "private"
    put = next(
        request
        for request in recorder.requests
        if request.method == "PUT" and request.url.path.endswith("/playlists")
    )
    assert put.url.params["part"] == "snippet,status"
    body = json.loads(put.content)
    assert body == {"id": "pl_1", "snippet": {"title": "Yeni Ad"}, "status": {"privacyStatus": "private"}}


def test_update_playlist_requires_at_least_one_field() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    with pytest.raises(ValueError):
        api.update_playlist("pl_1")

    assert not any(request.method == "PUT" for request in recorder.requests)


def test_update_playlist_rejects_foreign_playlist() -> None:
    api = build_api(Recorder(playlist_owner="UC_OTHER"))

    with pytest.raises(ChannelBindingMismatchException):
        api.update_playlist("pl_foreign", title="X")


def test_delete_playlist_checks_ownership_then_deletes() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    assert api.delete_playlist("pl_1") is True

    deletes = [
        request
        for request in recorder.requests
        if request.method == "DELETE" and request.url.path.endswith("/playlists")
    ]
    assert len(deletes) == 1
    assert deletes[0].url.params["id"] == "pl_1"


def test_delete_playlist_rejects_foreign_playlist() -> None:
    api = build_api(Recorder(playlist_owner="UC_OTHER"))

    with pytest.raises(ChannelBindingMismatchException):
        api.delete_playlist("pl_foreign")


def test_move_playlist_item_updates_position() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    assert api.move_playlist_item("pl_1", "vid_1", 3) is True

    put = next(
        request
        for request in recorder.requests
        if request.method == "PUT" and request.url.path.endswith("/playlistItems")
    )
    body = json.loads(put.content)
    assert body["id"] == "pli_1"
    assert body["snippet"]["playlistId"] == "pl_1"
    assert body["snippet"]["position"] == 3
    assert body["snippet"]["resourceId"]["videoId"] == "vid_1"


def test_move_playlist_item_returns_false_when_video_is_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=CHANNEL)
        if request.url.path.endswith("/playlists"):
            return httpx.Response(
                200,
                json={"items": [{"id": "pl_1", "snippet": {"channelId": "UC_REAL"}}]},
            )
        return httpx.Response(200, json={"items": []})

    api = YouTubeCreatorApi(
        CHANNEL_ACCESS, client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    assert api.move_playlist_item("pl_1", "vid_missing", 0) is False


def test_delete_video_checks_ownership_then_deletes() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    assert api.delete_video("vid_1") is True

    deletes = [
        request
        for request in recorder.requests
        if request.method == "DELETE" and request.url.path.endswith("/videos")
    ]
    assert len(deletes) == 1
    assert deletes[0].url.params["id"] == "vid_1"


def test_delete_video_rejects_foreign_video() -> None:
    recorder = Recorder()
    api = build_api(recorder)

    with pytest.raises(ChannelBindingMismatchException):
        api.delete_video("vid_foreign")

    assert not any(
        request.method == "DELETE" for request in recorder.requests
    )
