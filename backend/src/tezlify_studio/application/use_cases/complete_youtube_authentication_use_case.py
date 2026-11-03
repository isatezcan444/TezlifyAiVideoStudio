import uuid
from datetime import datetime, timezone, timedelta
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.publish_exceptions import AuthenticationRequiredException
from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.dto.publish_dto import SocialAccountDTO
from tezlify_studio.application.dto.mappers import social_account_to_dto
from tezlify_studio.application.use_cases.oauth_session_store import oauth_session_store

class CompleteYouTubeAuthenticationUseCase:
    def __init__(
        self,
        account_repo: SocialAccountRepositoryPort,
        token_storage: TokenStoragePort,
        publisher: YouTubePublisherPort,
    ):
        self.account_repo = account_repo
        self.token_storage = token_storage
        self.publisher = publisher

    def execute(self, code: str, state: str) -> SocialAccountDTO:
        verifier = oauth_session_store.consume_verifier(state)
        if not verifier:
            raise AuthenticationRequiredException("Geçersiz veya süresi dolmuş OAuth state oturumu.")

        # 1. Exchange authorization code with PKCE verifier
        tokens = self.publisher.exchange_code_for_tokens(code=code, code_verifier=verifier)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)

        if not access_token:
            raise AuthenticationRequiredException("Google'dan access_token alınamadı.")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # 2. Retrieve channel details
        profile = self.publisher.get_channel_profile(access_token)
        channel_id = profile.get("channel_id", "unknown_channel")
        channel_title = profile.get("channel_title", "YouTube Channel")
        channel_avatar = profile.get("avatar_url") or profile.get("channel_avatar")

        # 3. Save or update SocialAccount in repository
        existing = self.account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
        if existing:
            account = existing
            account.account_name = channel_title
            account.channel_id = channel_id
            account.channel_avatar_url = channel_avatar
            account.is_active = True
            account.token_expires_at = expires_at
            account.updated_at = datetime.now(timezone.utc)
        else:
            account = SocialAccount(
                id=str(uuid.uuid4()),
                platform=SocialPlatform.YOUTUBE,
                account_name=channel_title,
                channel_id=channel_id,
                channel_avatar_url=channel_avatar,
                is_active=True,
                token_expires_at=expires_at,
            )

        saved = self.account_repo.save(account)

        # 4. Securely store tokens in Keychain / TokenStorage
        self.token_storage.store_tokens(
            account_id=saved.id,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        return social_account_to_dto(saved)
