from typing import Optional
from datetime import datetime, timezone, timedelta
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.dto.publish_dto import SocialAccountDTO
from tezlify_studio.application.dto.mappers import social_account_to_dto

class GetConnectedYouTubeAccountUseCase:
    def __init__(
        self,
        account_repo: SocialAccountRepositoryPort,
        token_storage: TokenStoragePort,
        publisher: YouTubePublisherPort,
    ):
        self.account_repo = account_repo
        self.token_storage = token_storage
        self.publisher = publisher

    def execute(self) -> Optional[SocialAccountDTO]:
        account = self.account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
        if not account:
            return None

        # Check if access token is expired; auto-refresh if possible
        if account.is_token_expired():
            refresh_token = self.token_storage.get_refresh_token(account.id)
            if refresh_token:
                try:
                    refreshed = self.publisher.refresh_access_token(refresh_token)
                    new_access = refreshed.get("access_token")
                    expires_in = refreshed.get("expires_in", 3600)
                    if new_access:
                        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                        account.updated_at = datetime.now(timezone.utc)
                        self.account_repo.save(account)
                        self.token_storage.store_tokens(
                            account_id=account.id,
                            access_token=new_access,
                            refresh_token=refresh_token
                        )
                except Exception:
                    pass

        return social_account_to_dto(account)
