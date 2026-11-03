from typing import Optional
from sqlalchemy.orm import Session
from tezlify_studio.application.ports.social_account_repository_port import SocialAccountRepositoryPort
from tezlify_studio.domain.entities.social_account import SocialAccount
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.infrastructure.persistence.models.publish_models import SocialAccountModel

class SocialAccountRepositoryImpl(SocialAccountRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, model: SocialAccountModel) -> SocialAccount:
        return SocialAccount(
            id=model.id,
            platform=SocialPlatform(model.platform),
            account_name=model.account_name,
            channel_id=model.channel_id,
            channel_avatar_url=model.channel_avatar_url,
            is_active=model.is_active,
            token_expires_at=model.token_expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, account: SocialAccount) -> SocialAccount:
        model = self.db.query(SocialAccountModel).filter(SocialAccountModel.id == account.id).first()
        if not model:
            model = SocialAccountModel(
                id=account.id,
                platform=account.platform.value,
                account_name=account.account_name,
                channel_id=account.channel_id,
                channel_avatar_url=account.channel_avatar_url,
                is_active=account.is_active,
                token_expires_at=account.token_expires_at,
                created_at=account.created_at,
                updated_at=account.updated_at,
            )
            self.db.add(model)
        else:
            model.platform = account.platform.value
            model.account_name = account.account_name
            model.channel_id = account.channel_id
            model.channel_avatar_url = account.channel_avatar_url
            model.is_active = account.is_active
            model.token_expires_at = account.token_expires_at
            model.updated_at = account.updated_at

        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, account_id: str) -> Optional[SocialAccount]:
        model = self.db.query(SocialAccountModel).filter(SocialAccountModel.id == account_id).first()
        return self._to_domain(model) if model else None

    def get_active_by_platform(self, platform: SocialPlatform) -> Optional[SocialAccount]:
        model = (
            self.db.query(SocialAccountModel)
            .filter(
                SocialAccountModel.platform == platform.value,
                SocialAccountModel.is_active == True,
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def delete(self, account_id: str) -> bool:
        model = self.db.query(SocialAccountModel).filter(SocialAccountModel.id == account_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
