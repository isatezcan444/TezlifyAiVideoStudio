import subprocess
import shutil
import logging
from typing import Optional, Dict
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.domain.exceptions.publish_exceptions import TokenStorageException

logger = logging.getLogger(__name__)

class InMemoryTokenStorageAdapter(TokenStoragePort):
    """In-memory token store for testing and headless environments."""
    def __init__(self) -> None:
        self._tokens: Dict[str, Dict[str, Optional[str]]] = {}

    def store_tokens(
        self,
        account_id: str,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> None:
        current = self._tokens.get(account_id, {})
        new_refresh = refresh_token if refresh_token is not None else current.get("refresh")
        self._tokens[account_id] = {
            "access": access_token,
            "refresh": new_refresh,
        }

    def get_access_token(self, account_id: str) -> Optional[str]:
        return self._tokens.get(account_id, {}).get("access")

    def get_refresh_token(self, account_id: str) -> Optional[str]:
        return self._tokens.get(account_id, {}).get("refresh")

    def delete_tokens(self, account_id: str) -> None:
        self._tokens.pop(account_id, None)


class KeychainTokenStorageAdapter(TokenStoragePort):
    """
    Production macOS Keychain token storage using `/usr/bin/security`.
    Falls back to in-memory store if keychain CLI is unavailable or fails.
    """
    def __init__(self, fallback_to_memory: bool = True) -> None:
        self.service_prefix = "TezlifyStudio"
        self.fallback_to_memory = fallback_to_memory
        self.memory_fallback = InMemoryTokenStorageAdapter() if fallback_to_memory else None
        self.security_bin = shutil.which("security") or "/usr/bin/security"

    def _service_name(self, token_type: str) -> str:
        return f"{self.service_prefix}_{token_type}"

    def store_tokens(
        self,
        account_id: str,
        access_token: str,
        refresh_token: Optional[str] = None
    ) -> None:
        try:
            self._save_keychain_item(self._service_name("access"), account_id, access_token)
            if refresh_token is not None:
                self._save_keychain_item(self._service_name("refresh"), account_id, refresh_token)
        except Exception as e:
            if self.fallback_to_memory and self.memory_fallback:
                logger.warning("Keychain storage failed, falling back to memory store: %s", e)
                self.memory_fallback.store_tokens(account_id, access_token, refresh_token)
                return
            raise TokenStorageException(f"Failed to store tokens in Keychain: {str(e)}")

    def get_access_token(self, account_id: str) -> Optional[str]:
        try:
            token = self._read_keychain_item(self._service_name("access"), account_id)
            if token:
                return token
        except Exception as e:
            logger.warning("Keychain read error: %s", e)

        if self.fallback_to_memory and self.memory_fallback:
            return self.memory_fallback.get_access_token(account_id)
        return None

    def get_refresh_token(self, account_id: str) -> Optional[str]:
        try:
            token = self._read_keychain_item(self._service_name("refresh"), account_id)
            if token:
                return token
        except Exception as e:
            logger.warning("Keychain read error: %s", e)

        if self.fallback_to_memory and self.memory_fallback:
            return self.memory_fallback.get_refresh_token(account_id)
        return None

    def delete_tokens(self, account_id: str) -> None:
        try:
            self._delete_keychain_item(self._service_name("access"), account_id)
            self._delete_keychain_item(self._service_name("refresh"), account_id)
        except Exception as e:
            logger.warning("Keychain delete error: %s", e)

        if self.fallback_to_memory and self.memory_fallback:
            self.memory_fallback.delete_tokens(account_id)

    def _save_keychain_item(self, service: str, account: str, password: str) -> None:
        # -U updates the item if it already exists in the keychain
        cmd = [
            self.security_bin,
            "add-generic-password",
            "-U",
            "-a", account,
            "-s", service,
            "-w", password,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Keychain add failed: {res.stderr.strip()}")

    def _read_keychain_item(self, service: str, account: str) -> Optional[str]:
        cmd = [
            self.security_bin,
            "find-generic-password",
            "-s", service,
            "-a", account,
            "-w",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
        # Return code 44 means item not found
        return None

    def _delete_keychain_item(self, service: str, account: str) -> None:
        cmd = [
            self.security_bin,
            "delete-generic-password",
            "-s", service,
            "-a", account,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # returncode 44 is not found, which is fine when deleting
