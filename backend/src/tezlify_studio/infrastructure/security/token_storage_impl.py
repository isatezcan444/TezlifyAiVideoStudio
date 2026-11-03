import os
import shutil
import subprocess
import logging
from typing import Optional, Dict
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.domain.exceptions.publish_exceptions import TokenStorageException

logger = logging.getLogger(__name__)

class InMemoryTokenStorageAdapter(TokenStoragePort):
    """
    In-memory token store strictly dedicated for automated testing, CI,
    and simulated regression runners.
    """
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
    Strict Security Guarantee: Does NOT silently fall back to volatile memory in production.
    If Keychain fails or access is denied, halts with an explicit TokenStorageException.
    """
    def __init__(self, fallback_to_memory: bool = False) -> None:
        self.service_prefix = "TezlifyStudio"
        self.fallback_to_memory = fallback_to_memory
        self.memory_fallback = InMemoryTokenStorageAdapter() if fallback_to_memory else None
        self.security_bin = shutil.which("security") or "/usr/bin/security"

        if not os.path.exists(self.security_bin):
            if not self.fallback_to_memory:
                raise TokenStorageException(f"macOS security aracı bulunamadı: {self.security_bin}")

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
            if isinstance(e, TokenStorageException):
                raise
            raise TokenStorageException(f"macOS Keychain token kaydı başarısız: {str(e)}")

    def get_access_token(self, account_id: str) -> Optional[str]:
        try:
            return self._read_keychain_item(self._service_name("access"), account_id)
        except Exception as e:
            if self.fallback_to_memory and self.memory_fallback:
                logger.warning("Keychain read failed, falling back to memory store: %s", e)
                return self.memory_fallback.get_access_token(account_id)
            if isinstance(e, TokenStorageException):
                raise
            raise TokenStorageException(f"macOS Keychain access token okunamadı: {str(e)}")

    def get_refresh_token(self, account_id: str) -> Optional[str]:
        try:
            return self._read_keychain_item(self._service_name("refresh"), account_id)
        except Exception as e:
            if self.fallback_to_memory and self.memory_fallback:
                logger.warning("Keychain read failed, falling back to memory store: %s", e)
                return self.memory_fallback.get_refresh_token(account_id)
            if isinstance(e, TokenStorageException):
                raise
            raise TokenStorageException(f"macOS Keychain refresh token okunamadı: {str(e)}")

    def delete_tokens(self, account_id: str) -> None:
        try:
            self._delete_keychain_item(self._service_name("access"), account_id)
            self._delete_keychain_item(self._service_name("refresh"), account_id)
        except Exception as e:
            if self.fallback_to_memory and self.memory_fallback:
                logger.warning("Keychain delete failed, falling back to memory store: %s", e)
                self.memory_fallback.delete_tokens(account_id)
                return
            if isinstance(e, TokenStorageException):
                raise
            raise TokenStorageException(f"macOS Keychain token silme başarısız: {str(e)}")

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
            err = res.stderr.strip()
            raise TokenStorageException(
                f"macOS Keychain kaydı başarısız (Çıkış kodu: {res.returncode}): {err}"
            )

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
        # Return code 44 means item not found (normal empty state)
        if res.returncode == 44:
            return None
        err = res.stderr.strip()
        raise TokenStorageException(
            f"macOS Keychain erişimi reddedildi veya hata oluştu (Çıkış kodu: {res.returncode}): {err}"
        )

    def _delete_keychain_item(self, service: str, account: str) -> None:
        cmd = [
            self.security_bin,
            "delete-generic-password",
            "-s", service,
            "-a", account,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Return code 44 means item not found, which is a success condition during deletion
        if res.returncode in (0, 44):
            return
        err = res.stderr.strip()
        raise TokenStorageException(
            f"macOS Keychain silme hatası (Çıkış kodu: {res.returncode}): {err}"
        )
