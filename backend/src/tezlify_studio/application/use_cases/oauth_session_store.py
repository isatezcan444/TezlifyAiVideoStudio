import time
import secrets
import hashlib
import base64
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from tezlify_studio.domain.exceptions.creator_exceptions import (
    DuplicateOAuthCallbackException,
)

INTENT_ADD_ACCOUNT = "add_account"
INTENT_RECONNECT = "reconnect"


@dataclass(frozen=True)
class OAuthSession:
    state: str
    code_verifier: str
    redirect_uri: Optional[str]
    intent: str
    connection_id: Optional[str]
    created_at: float
    capabilities: List[str] = field(default_factory=list)
    requested_scopes: List[str] = field(default_factory=list)


class OAuthSessionStore:
    """
    In-memory thread-safe storage for pending OAuth state, PKCE verifiers,
    and associated dynamic loopback redirect URIs.
    Enforces TTL (10 minutes) and single-use validation (CSRF prevention).
    """

    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, OAuthSession] = {}
        self._consumed: Dict[str, float] = {}
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

    def create_session(
        self,
        redirect_uri: Optional[str] = None,
        intent: str = INTENT_ADD_ACCOUNT,
        connection_id: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        requested_scopes: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """
        Creates a new OAuth state and PKCE pair with optional dynamic redirect_uri.
        Returns: (state, code_challenge)
        """
        state = secrets.token_urlsafe(32)
        verifier, challenge = self.generate_pkce()
        session = OAuthSession(
            state=state,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
            intent=intent,
            connection_id=connection_id,
            created_at=time.time(),
            capabilities=list(capabilities or []),
            requested_scopes=list(requested_scopes or []),
        )
        with self._lock:
            self._cleanup_expired_locked()
            self._sessions[state] = session
        return state, challenge

    def consume_session(self, state: str) -> Optional[OAuthSession]:
        """
        Validates state, returns the session, and marks it consumed.

        A state that was already used raises ``DuplicateOAuthCallbackException``
        so a repeated browser callback cannot overwrite an existing connection.
        """
        with self._lock:
            self._cleanup_expired_locked()
            session = self._sessions.pop(state, None)
            if session is None:
                if state in self._consumed:
                    raise DuplicateOAuthCallbackException()
                return None
            if time.time() - session.created_at > self.ttl_seconds:
                return None
            self._consumed[state] = time.time()
            return session

    def consume_verifier(self, state: str) -> Optional[str]:
        """
        Backward-compatible helper returning only the verifier.
        """
        try:
            session = self.consume_session(state)
        except DuplicateOAuthCallbackException:
            return None
        return session.code_verifier if session else None

    def _cleanup_expired_locked(self) -> None:
        now = time.time()
        expired = [
            state
            for state, session in self._sessions.items()
            if now - session.created_at > self.ttl_seconds
        ]
        for state in expired:
            self._sessions.pop(state, None)
        stale = [
            state
            for state, consumed_at in self._consumed.items()
            if now - consumed_at > self.ttl_seconds
        ]
        for state in stale:
            self._consumed.pop(state, None)


oauth_session_store = OAuthSessionStore()
