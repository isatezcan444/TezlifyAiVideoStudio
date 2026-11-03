import uuid
import sys
import pytest
from tezlify_studio.infrastructure.security.token_storage_impl import (
    KeychainTokenStorageAdapter,
    TokenStorageException,
)

@pytest.mark.skipif(sys.platform != "darwin", reason="Only runs on macOS")
def test_real_macos_keychain_store_read_delete():
    adapter = KeychainTokenStorageAdapter(fallback_to_memory=False)
    test_account_id = f"test_acc_{uuid.uuid4().hex[:12]}"
    test_access = f"access_secret_{uuid.uuid4().hex}"
    test_refresh = f"refresh_secret_{uuid.uuid4().hex}"

    try:
        # Initially empty (errSecItemNotFound / 44)
        assert adapter.get_access_token(test_account_id) is None
        assert adapter.get_refresh_token(test_account_id) is None

        # Store tokens
        adapter.store_tokens(test_account_id, test_access, test_refresh)

        # Retrieve and verify tokens
        assert adapter.get_access_token(test_account_id) == test_access
        assert adapter.get_refresh_token(test_account_id) == test_refresh

        # Update access token
        updated_access = f"updated_access_{uuid.uuid4().hex}"
        adapter.store_tokens(test_account_id, updated_access)
        assert adapter.get_access_token(test_account_id) == updated_access
        assert adapter.get_refresh_token(test_account_id) == test_refresh

        # Delete tokens
        adapter.delete_tokens(test_account_id)

        # Verify deletion
        assert adapter.get_access_token(test_account_id) is None
        assert adapter.get_refresh_token(test_account_id) is None

    finally:
        # Ensure cleanup
        adapter.delete_tokens(test_account_id)

def test_keychain_missing_binary_raises_exception():
    adapter = KeychainTokenStorageAdapter(fallback_to_memory=False)
    adapter.security_bin = "/nonexistent/path/to/security_cli"

    with pytest.raises(TokenStorageException):
        adapter.store_tokens("dummy_id", "access", "refresh")
