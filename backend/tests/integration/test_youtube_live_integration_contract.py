import pytest
import httpx
from unittest.mock import patch
from fastapi.testclient import TestClient

from tezlify_studio.presentation.api.app import app
from tezlify_studio.infrastructure.media.youtube_api_client_impl import YouTubeApiClientImpl
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
    PublishDomainException,
)
from tezlify_studio.infrastructure.security.oauth_desktop_listener import DesktopOAuthListener
from tezlify_studio.infrastructure.security.token_storage_impl import KeychainTokenStorageAdapter


def test_missing_google_client_id_raises_clear_auth_error():
    """Verify that if GOOGLE_CLIENT_ID is not configured, a clear 401 error is raised and listener is cleaned up."""
    from tezlify_studio.presentation.dependencies.container import get_youtube_publisher
    
    unconfigured_publisher = YouTubeApiClientImpl(client_id=None)
    app.dependency_overrides[get_youtube_publisher] = lambda: unconfigured_publisher
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/social/youtube/connect")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error_code"] == "AUTHENTICATION_REQUIRED"
        assert "GOOGLE_CLIENT_ID" in data["detail"]
        # Ensure listener was stopped and cleaned up
        assert DesktopOAuthListener._current_listener is None
    finally:
        app.dependency_overrides.pop(get_youtube_publisher, None)


def test_refresh_token_revoked_invalid_grant_error_handling():
    """Verify that Google returning invalid_grant (revoked or expired refresh token) produces a clear actionable message."""
    resp_invalid_grant = httpx.Response(
        400,
        headers={"content-type": "application/json"},
        json={
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked.",
        },
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: resp_invalid_grant))
    yt = YouTubeApiClientImpl(client_id="test_client_id", client=mock_client)

    with pytest.raises(AuthenticationRequiredException) as exc_info:
        yt.refresh_access_token("revoked_refresh_token")

    err_msg = str(exc_info.value)
    assert "Google yetkilendirme anahtarının (refresh token) süresi dolmuş veya yetki geri çekilmiş" in err_msg


def test_initiate_resumable_upload_bad_request_400_handling():
    """Verify that HTTP 400 from YouTube during upload initiation extracts error.message."""
    resp_bad_req = httpx.Response(
        400,
        headers={"content-type": "application/json"},
        json={
            "error": {
                "message": "Invalid video category specified: 99999",
                "code": 400,
            }
        },
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: resp_bad_req))
    yt = YouTubeApiClientImpl(client_id="test_client_id", client=mock_client)

    with pytest.raises(PublishDomainException) as exc_info:
        yt.initiate_resumable_upload(
            access_token="fake_token",
            title="Test Title",
            description="Test Description",
            tags=["test"],
            category_id="99999",
            privacy="private",
            total_bytes=1000,
        )

    assert "YouTube video parametre hatası (HTTP 400)" in str(exc_info.value)
    assert "Invalid video category specified" in str(exc_info.value)


def test_get_channel_profile_no_channels_found_guidance():
    """Verify that if user's Google account has 0 channels, a helpful instruction message is returned."""
    resp_empty_channels = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={"kind": "youtube#channelListResponse", "items": []},
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: resp_empty_channels))
    yt = YouTubeApiClientImpl(client_id="test_client_id", client=mock_client)

    with pytest.raises(PublishDomainException) as exc_info:
        yt.get_channel_profile(access_token="fake_token")

    assert "YouTube Studio üzerinde bir kanal oluşturun" in str(exc_info.value)


def test_desktop_oauth_pkce_url_conformance():
    """Verify that generate_auth_url enforces RFC 7636 PKCE S256 with loopback 127.0.0.1 redirect."""
    yt = YouTubeApiClientImpl(client_id="test_client_id", redirect_uri="http://127.0.0.1:54321/oauth2callback")
    auth_url = yt.generate_auth_url(state="test_state_123", code_challenge="test_challenge_abc")

    assert "https://accounts.google.com/o/oauth2/v2/auth" in auth_url
    assert "client_id=test_client_id" in auth_url
    assert "code_challenge=test_challenge_abc" in auth_url
    assert "code_challenge_method=S256" in auth_url
    assert "response_type=code" in auth_url
    assert "access_type=offline" in auth_url
    assert "prompt=consent" in auth_url
    assert "state=test_state_123" in auth_url
