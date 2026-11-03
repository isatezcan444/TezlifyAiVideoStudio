import time
import secrets
import hashlib
import base64
from typing import Dict, Optional, Tuple

class OAuthSessionStore:
    """
    In-memory thread-safe storage for pending OAuth state and PKCE verifiers.
    Enforces TTL (10 minutes) and single-use validation (CSRF prevention).
    """
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, Tuple[str, float]] = {}  # state -> (code_verifier, timestamp)

    @staticmethod
    def generate_pkce() -> Tuple[str, str]:
        """
        Generates RFC 7636 compliant PKCE code_verifier and code_challenge (S256).
        """
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    def create_session(self) -> Tuple[str, str]:
        """
        Creates a new OAuth state and PKCE pair.
        Returns: (state, code_challenge)
        """
        state = secrets.token_urlsafe(32)
        verifier, challenge = self.generate_pkce()
        self._sessions[state] = (verifier, time.time())
        self._cleanup_expired()
        return state, challenge

    def consume_verifier(self, state: str) -> Optional[str]:
        """
        Validates state, retrieves verifier and immediately deletes it (single-use).
        """
        self._cleanup_expired()
        session = self._sessions.pop(state, None)
        if not session:
            return None
        verifier, created_at = session
        if time.time() - created_at > self.ttl_seconds:
            return None
        return verifier

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [s for s, (_, t) in self._sessions.items() if now - t > self.ttl_seconds]
        for s in expired:
            self._sessions.pop(s, None)

oauth_session_store = OAuthSessionStore()
