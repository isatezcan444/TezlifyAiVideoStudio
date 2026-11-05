import socket
import logging
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler for Google Desktop OAuth Loopback.
    Strictly bound to 127.0.0.1.
    Never logs authorization codes or credentials.
    """
    server: "DesktopOAuthServer"

    def log_message(self, format: str, *args: Any) -> None:
        # Security: Override default logging to prevent leaking '?code=...' to stdout/stderr
        logger.debug("Desktop OAuth loopback request processed on 127.0.0.1:%s", self.server.server_port)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]

        if error:
            logger.info("Google OAuth canceled or returned error: %s", error)
            self._render_response(
                status_code=400,
                title="Yetkilendirme İptal Edildi",
                message=f"Google tarafından yetkilendirme iptal edildi veya hata oluştu: <strong>{error}</strong>",
                is_error=True,
            )
            self.server.notify_result(error=error)
            self.server.schedule_shutdown()
            return

        if not code or not state:
            self._render_response(
                status_code=400,
                title="Eksik Parametreler",
                message="Google dönüşünde yetkilendirme kodu (code) veya oturum durumu (state) bulunamadı.",
                is_error=True,
            )
            self.server.notify_result(error="missing_parameters")
            self.server.schedule_shutdown()
            return

        # Complete authentication via server callback
        try:
            account_dto = self.server.handle_oauth_code(code=code, state=state)
            channel_name = (
                account_dto.account_display_name
                if account_dto and getattr(account_dto, "account_display_name", None)
                else "YouTube Kanalı"
            )
            self._render_response(
                status_code=200,
                title="Yetkilendirme Başarılı",
                message=f"<strong>{channel_name}</strong> başarıyla bağlandı ve anahtarlar macOS Keychain'e güvenle kaydedildi.",
                is_error=False,
            )
            self.server.notify_result(success=True)
        except Exception as e:
            logger.error("OAuth token takası hatası: %s", e)
            self._render_response(
                status_code=400,
                title="Bağlantı Hatası",
                message=f"Yetkilendirme kodu doğrulanırken hata oluştu: {str(e)}",
                is_error=True,
            )
            self.server.notify_result(error=str(e))
        finally:
            self.server.schedule_shutdown()

    def _render_response(self, status_code: int, title: str, message: str, is_error: bool) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        color = "#ef4444" if is_error else "#10b981"
        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>{title} - Tezlify AI Video Studio</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0b0f19;
            color: #f3f4f6;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #111827;
            border: 1px solid {color};
            border-radius: 14px;
            padding: 36px;
            max-width: 480px;
            text-align: center;
            box-shadow: 0 15px 35px rgba(0,0,0,0.6);
        }}
        h1 {{ color: {color}; font-size: 22px; margin-bottom: 12px; }}
        p {{ color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 24px; }}
        button {{
            background: #7367F0;
            color: #fff;
            border: none;
            padding: 10px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }}
    </style>
    <script>
        setTimeout(() => {{
            try {{ window.close(); }} catch(e) {{}}
        }}, 3000);
    </script>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
        <p style="font-size: 12px; color: #6b7280;">Bu sekmeyi kapatabilir ve Tezlify AI Video Studio'ya dönebilirsiniz.</p>
        <button onclick="window.close()">Sekmeyi Kapat</button>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))


class DesktopOAuthServer(HTTPServer):
    def __init__(
        self,
        server_address: Tuple[str, int],
        oauth_handler_cb: Callable[[str, str], Any],
        on_complete_cb: Optional[Callable[..., Any]] = None,
    ):
        super().__init__(server_address, _OAuthCallbackHandler)
        self.oauth_handler_cb = oauth_handler_cb
        self.on_complete_cb = on_complete_cb
        self._is_shutting_down = False

    def handle_oauth_code(self, code: str, state: str) -> Any:
        return self.oauth_handler_cb(code, state)

    def notify_result(self, success: bool = False, error: Optional[str] = None) -> None:
        if self.on_complete_cb:
            try:
                self.on_complete_cb(success=success, error=error)
            except Exception as e:
                logger.warning("on_complete_cb error: %s", e)

    def schedule_shutdown(self) -> None:
        if self._is_shutting_down:
            return
        self._is_shutting_down = True

        def _delayed():
            import time
            time.sleep(0.05)
            try:
                self.shutdown()
                self.server_close()
            except Exception:
                pass

        threading.Thread(target=_delayed, daemon=True).start()


class DesktopOAuthListener:
    """
    Manages ephemeral Desktop App OAuth loopback listener on 127.0.0.1:{dynamic_port}.
    Conforms to RFC 8252 and Google's official Native App specifications.
    """
    _current_listener: Optional["DesktopOAuthListener"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        oauth_handler_cb: Callable[[str, str], Any],
        timeout_seconds: int = 300,
    ):
        self.oauth_handler_cb = oauth_handler_cb
        self.timeout_seconds = timeout_seconds
        self.server: Optional[DesktopOAuthServer] = None
        self.port: int = 0
        self.redirect_uri: str = ""
        self._thread: Optional[threading.Thread] = None
        self._timer: Optional[threading.Timer] = None

    @classmethod
    def start_new(
        cls,
        oauth_handler_cb: Callable[[str, str], Any],
        timeout_seconds: int = 300,
    ) -> "DesktopOAuthListener":
        with cls._lock:
            if cls._current_listener:
                cls._current_listener.stop()
            listener = cls(oauth_handler_cb, timeout_seconds)
            listener._start()
            cls._current_listener = listener
            return listener

    @classmethod
    def stop_current(cls) -> None:
        with cls._lock:
            if cls._current_listener:
                cls._current_listener.stop()
                cls._current_listener = None

    def _start(self) -> None:
        # Bind strictly to 127.0.0.1 on ephemeral port (0)
        self.server = DesktopOAuthServer(
            ("127.0.0.1", 0),
            oauth_handler_cb=self.oauth_handler_cb,
            on_complete_cb=self._on_server_finished,
        )
        self.port = self.server.server_port
        self.redirect_uri = f"http://127.0.0.1:{self.port}/oauth2callback"
        logger.info("Started Desktop OAuth loopback listener on %s", self.redirect_uri)

        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

        # Automatic timeout to release socket if user closes browser
        self._timer = threading.Timer(self.timeout_seconds, self.stop)
        self._timer.daemon = True
        self._timer.start()

    def _on_server_finished(self, success: bool = False, error: Optional[str] = None) -> None:
        # Callback notified; server will shutdown cleanly via schedule_shutdown
        pass

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self.server:
            try:
                self.server.schedule_shutdown()
            except Exception:
                pass
            self.server = None
        logger.debug("Desktop OAuth loopback listener stopped.")
