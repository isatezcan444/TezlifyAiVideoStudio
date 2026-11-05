import time
from types import SimpleNamespace

import httpx

from tezlify_studio.infrastructure.security.oauth_desktop_listener import DesktopOAuthListener

def test_desktop_oauth_listener_success_callback():
    received_code = None
    received_state = None

    def fake_handler(code: str, state: str):
        nonlocal received_code, received_state
        received_code = code
        received_state = state
        return SimpleNamespace(account_display_name="Test Channel")

    listener = DesktopOAuthListener.start_new(oauth_handler_cb=fake_handler, timeout_seconds=10)
    try:
        assert listener.port > 1024
        assert listener.redirect_uri == f"http://127.0.0.1:{listener.port}/oauth2callback"

        # Make HTTP request simulating Google browser redirect
        url = f"{listener.redirect_uri}?code=auth_code_xyz&state=state_secret_789"
        resp = httpx.get(url, timeout=5.0)

        assert resp.status_code == 200
        assert "Yetkilendirme Başarılı" in resp.text
        assert "Test Channel" in resp.text
        assert received_code == "auth_code_xyz"
        assert received_state == "state_secret_789"

        # Allow shutdown thread to complete
        time.sleep(0.3)
        assert listener.server._is_shutting_down is True
        listener.stop()
        assert listener.server is None
    finally:
        listener.stop()

def test_desktop_oauth_listener_error_callback():
    def dummy_handler(code: str, state: str):
        return None

    listener = DesktopOAuthListener.start_new(oauth_handler_cb=dummy_handler, timeout_seconds=10)
    try:
        url = f"{listener.redirect_uri}?error=access_denied"
        resp = httpx.get(url, timeout=5.0)

        assert resp.status_code == 400
        assert "Yetkilendirme İptal Edildi" in resp.text

        time.sleep(0.3)
        assert listener.server._is_shutting_down is True
        listener.stop()
        assert listener.server is None
    finally:
        listener.stop()
