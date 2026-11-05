import json
from datetime import timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.connection_status import ConnectionStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.infrastructure.persistence.models.connection_models import (
    PlatformConnectionModel,
)


class PlatformConnectionRepositoryImpl(PlatformConnectionRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ensure_utc(value):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _to_domain(self, model: PlatformConnectionModel) -> PlatformConnection:
        try:
            scopes = json.loads(model.granted_scopes_json or "[]")
        except Exception:
            scopes = []
        return PlatformConnection(
            id=model.id,
            platform=SocialPlatform(model.platform),
            account_external_id=model.account_external_id,
            account_display_name=model.account_display_name,
            connection_status=ConnectionStatus(model.connection_status),
            token_reference=model.token_reference,
            granted_scopes=scopes,
            connected_at=self._ensure_utc(model.connected_at),
            last_refreshed_at=self._ensure_utc(model.last_refreshed_at),
            token_expires_at=self._ensure_utc(model.token_expires_at),
            created_at=self._ensure_utc(model.created_at),
            updated_at=self._ensure_utc(model.updated_at),
        )

    def save(self, connection: PlatformConnection) -> PlatformConnection:
        model = (
            self.db.query(PlatformConnectionModel)
            .filter(PlatformConnectionModel.id == connection.id)
            .first()
        )
        scopes_json = json.dumps(connection.granted_scopes or [])
        if not model:
            model = PlatformConnectionModel(
                id=connection.id,
                platform=connection.platform.value,
                account_external_id=connection.account_external_id,
                account_display_name=connection.account_display_name,
                connection_status=connection.connection_status.value,
                token_reference=connection.token_reference,
                granted_scopes_json=scopes_json,
                connected_at=connection.connected_at,
                last_refreshed_at=connection.last_refreshed_at,
                token_expires_at=connection.token_expires_at,
                created_at=connection.created_at,
                updated_at=connection.updated_at,
            )
            self.db.add(model)
        else:
            model.platform = connection.platform.value
            model.account_external_id = connection.account_external_id
            model.account_display_name = connection.account_display_name
            model.connection_status = connection.connection_status.value
            model.token_reference = connection.token_reference
            model.granted_scopes_json = scopes_json
            model.last_refreshed_at = connection.last_refreshed_at
            model.token_expires_at = connection.token_expires_at
            model.updated_at = connection.updated_at

        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, connection_id: str) -> Optional[PlatformConnection]:
        model = (
            self.db.query(PlatformConnectionModel)
            .filter(PlatformConnectionModel.id == connection_id)
            .first()
        )
        return self._to_domain(model) if model else None

    def get_by_platform_account(
        self, platform: str, account_external_id: str
    ) -> Optional[PlatformConnection]:
        model = (
            self.db.query(PlatformConnectionModel)
            .filter(
                PlatformConnectionModel.platform == platform,
                PlatformConnectionModel.account_external_id == account_external_id,
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def list_by_platform(
        self, platform: str, include_disconnected: bool = False
    ) -> List[PlatformConnection]:
        query = self.db.query(PlatformConnectionModel).filter(
            PlatformConnectionModel.platform == platform
        )
        if not include_disconnected:
            query = query.filter(
                PlatformConnectionModel.connection_status != ConnectionStatus.DISCONNECTED.value
            )
        models = query.order_by(PlatformConnectionModel.connected_at.asc()).all()
        return [self._to_domain(model) for model in models]

    def list_all(self, include_disconnected: bool = False) -> List[PlatformConnection]:
        query = self.db.query(PlatformConnectionModel)
        if not include_disconnected:
            query = query.filter(
                PlatformConnectionModel.connection_status != ConnectionStatus.DISCONNECTED.value
            )
        models = query.order_by(PlatformConnectionModel.connected_at.asc()).all()
        return [self._to_domain(model) for model in models]

    def count(self) -> int:
        return self.db.query(PlatformConnectionModel).count()

    def delete(self, connection_id: str) -> bool:
        model = (
            self.db.query(PlatformConnectionModel)
            .filter(PlatformConnectionModel.id == connection_id)
            .first()
        )
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
