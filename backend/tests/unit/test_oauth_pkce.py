import time
from tezlify_studio.application.use_cases.oauth_session_store import (
    OAuthSessionStore,
    oauth_session_store,
)

def test_pkce_generation():
    verifier, challenge = OAuthSessionStore.generate_pkce()
    assert len(verifier) >= 43
    assert challenge is not None
    assert len(challenge) > 20
    # Challenge must not contain padding '='
    assert "=" not in challenge

def test_oauth_session_lifecycle():
    store = OAuthSessionStore(ttl_seconds=5)
    state, challenge = store.create_session()

    assert state is not None
    assert challenge is not None

    # Consume verifier
    retrieved = store.consume_verifier(state)
    assert retrieved is not None
    assert len(retrieved) >= 43

    # Second consumption must return None (single-use CSRF token)
    second_try = store.consume_verifier(state)
    assert second_try is None

def test_oauth_session_ttl_expiration():
    store = OAuthSessionStore(ttl_seconds=1)
    state, _ = store.create_session()

    time.sleep(1.1)

    # State has expired
    consumed = store.consume_verifier(state)
    assert consumed is None
