import time
import secrets
import hashlib
import base64
import threading
from typing import Dict, Optional, Tuple

class OAuthSessionStore:
    """
    In-memory thread-safe storage for pending OAuth state, PKCE verifiers,
    and associated dynamic loopback redirect URIs.
    Enforces TTL (10 minutes) and single-use validation (CSRF prevention).
    """
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        # state -> (code_verifier, redirect_uri, created_at)
        self._sessions: Dict[str, Tuple[str, Optional[str], float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def generate_pkce() -> Tuple[str, str]:
        """
        Generates RFC 7636 compliant PKCE code_verifier and code_challenge (S256).
        """
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    def create_session(self, redirect_uri: Optional[str] = None) -> Tuple[str, str]:
        """
        Creates a new OAuth state and PKCE pair with optional dynamic redirect_uri.
        Returns: (state, code_challenge)
        """
        state = secrets.token_urlsafe(32)
        verifier, challenge = self.generate_pkce()
        with self._lock:
            self._sessions[state] = (verifier, redirect_uri, time.time())
            self._cleanup_expired_locked()
        return state, challenge

    def consume_session(self, state: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Validates state, retrieves (verifier, redirect_uri), and immediately deletes it (single-use CSRF).
        """
        with self._lock:
            self._cleanup_expired_locked()
            session = self._sessions.pop(state, None)
            if not session:
                return None
            verifier, redirect_uri, created_at = session
            if time.time() - created_at > self.ttl_seconds:
                return None
            return verifier, redirect_uri

    def consume_verifier(self, state: str) -> Optional[str]:
        """
        Backward-compatible helper returning only the verifier.
        """
        res = self.consume_session(state)
        return res[0] if res else None

    def _cleanup_expired_locked(self) -> None:
        now = time.time()
        expired = [s for s, (_, _, t) in self._sessions.items() if now - t > self.ttl_seconds]
        for s in expired:
            self._sessions.pop(s, None)

oauth_session_store = OAuthSessionStore()
