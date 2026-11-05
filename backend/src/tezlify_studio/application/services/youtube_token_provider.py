from datetime import datetime, timedelta, timezone
from typing import Optional

from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
    SocialAccountNotFoundException,
)


class YouTubeTokenProvider:
    """Resolves an active YouTube account and a usable access token.

    Refresh happens only when the stored expiry says the token is stale, so the
    existing Keychain grant keeps working without a new OAuth round-trip.
    """

    def __init__(
        self,
        account_repo: SocialAccountRepositoryPort,
        token_storage: TokenStoragePort,
        publisher: YouTubePublisherPort,
    ) -> None:
        self.account_repo = account_repo
        self.token_storage = token_storage
        self.publisher = publisher

    def get_account(self) -> SocialAccount:
        account = self.account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
        if not account:
            raise SocialAccountNotFoundException("youtube")
        return account

    def get_access_token(self) -> str:
        account = self.get_account()
        access_token = self.token_storage.get_access_token(account.id)
        if access_token and not account.is_token_expired():
            return access_token

        refresh_token = self.token_storage.get_refresh_token(account.id)
        if not refresh_token:
            raise AuthenticationRequiredException(
                "YouTube oturumunun yenileme anahtarı bulunamadı. Lütfen hesabı yeniden bağlayın."
            )

        refreshed = self.publisher.refresh_access_token(refresh_token)
        new_access = refreshed.get("access_token")
        if not new_access:
            raise AuthenticationRequiredException("YouTube erişim anahtarı yenilenemedi.")

        expires_in = int(refreshed.get("expires_in", 3600))
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(expires_in - 120, 60)
        )
        account.updated_at = datetime.now(timezone.utc)
        self.account_repo.save(account)
        self.token_storage.store_tokens(account.id, new_access, refresh_token)
        return new_access
