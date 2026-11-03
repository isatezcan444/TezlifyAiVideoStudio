from tezlify_studio.infrastructure.security.token_storage_impl import (
    InMemoryTokenStorageAdapter,
    KeychainTokenStorageAdapter,
)

def test_in_memory_token_storage():
    storage = InMemoryTokenStorageAdapter()
    account_id = "test-account-123"

    # Initially empty
    assert storage.get_access_token(account_id) is None
    assert storage.get_refresh_token(account_id) is None

    # Store tokens
    storage.store_tokens(account_id, access_token="access-abc", refresh_token="refresh-xyz")
    assert storage.get_access_token(account_id) == "access-abc"
    assert storage.get_refresh_token(account_id) == "refresh-xyz"

    # Update only access token; refresh token remains preserved
    storage.store_tokens(account_id, access_token="access-new")
    assert storage.get_access_token(account_id) == "access-new"
    assert storage.get_refresh_token(account_id) == "refresh-xyz"

    # Delete tokens
    storage.delete_tokens(account_id)
    assert storage.get_access_token(account_id) is None
    assert storage.get_refresh_token(account_id) is None

def test_keychain_storage_fallback():
    # When initialized with fallback_to_memory=True, gracefully handles operations
    storage = KeychainTokenStorageAdapter(fallback_to_memory=True)
    account_id = "test-keychain-fallback-id"

    storage.store_tokens(account_id, "token_123", "refresh_123")
    assert storage.get_access_token(account_id) == "token_123"
    assert storage.get_refresh_token(account_id) == "refresh_123"

    storage.delete_tokens(account_id)
    assert storage.get_access_token(account_id) is None
