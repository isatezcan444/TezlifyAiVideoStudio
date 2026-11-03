from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort

class DisconnectYouTubeAccountUseCase:
    def __init__(
        self,
        account_repo: SocialAccountRepositoryPort,
        token_storage: TokenStoragePort,
    ):
        self.account_repo = account_repo
        self.token_storage = token_storage

    def execute(self) -> bool:
        account = self.account_repo.get_active_by_platform(SocialPlatform.YOUTUBE)
        if not account:
            return False

        # 1. Purge secrets from Keychain / TokenStorage
        self.token_storage.delete_tokens(account.id)

        # 2. Delete account record from database
        return self.account_repo.delete(account.id)
