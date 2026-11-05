import json
from datetime import timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.infrastructure.persistence.models.connection_models import (
    PlatformChannelModel,
)


class PlatformChannelRepositoryImpl(PlatformChannelRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ensure_utc(value):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _to_domain(self, model: PlatformChannelModel) -> PlatformChannel:
        try:
            metadata = json.loads(model.metadata_json or "{}")
        except Exception:
            metadata = {}
        return PlatformChannel(
            id=model.id,
            platform_connection_id=model.platform_connection_id,
            platform=SocialPlatform(model.platform),
            channel_external_id=model.channel_external_id,
            channel_name=model.channel_name,
            channel_handle=model.channel_handle,
            avatar_url=model.avatar_url,
            description=model.description or "",
            is_primary=bool(model.is_primary),
            is_enabled=bool(model.is_enabled),
            subscriber_count=model.subscriber_count,
            uploads_playlist_id=model.uploads_playlist_id,
            metadata=metadata,
            created_at=self._ensure_utc(model.created_at),
            updated_at=self._ensure_utc(model.updated_at),
        )

    def save(self, channel: PlatformChannel) -> PlatformChannel:
        model = (
            self.db.query(PlatformChannelModel)
            .filter(PlatformChannelModel.id == channel.id)
            .first()
        )
        metadata_json = json.dumps(channel.metadata or {})
        if not model:
            model = PlatformChannelModel(
                id=channel.id,
                platform_connection_id=channel.platform_connection_id,
                platform=channel.platform.value,
                channel_external_id=channel.channel_external_id,
                channel_name=channel.channel_name,
                channel_handle=channel.channel_handle,
                avatar_url=channel.avatar_url,
                description=channel.description,
                is_primary=channel.is_primary,
                is_enabled=channel.is_enabled,
                subscriber_count=channel.subscriber_count,
                uploads_playlist_id=channel.uploads_playlist_id,
                metadata_json=metadata_json,
                created_at=channel.created_at,
                updated_at=channel.updated_at,
            )
            self.db.add(model)
        else:
            model.platform_connection_id = channel.platform_connection_id
            model.platform = channel.platform.value
            model.channel_external_id = channel.channel_external_id
            model.channel_name = channel.channel_name
            model.channel_handle = channel.channel_handle
            model.avatar_url = channel.avatar_url
            model.description = channel.description
            model.is_primary = channel.is_primary
            model.is_enabled = channel.is_enabled
            model.subscriber_count = channel.subscriber_count
            model.uploads_playlist_id = channel.uploads_playlist_id
            model.metadata_json = metadata_json
            model.updated_at = channel.updated_at

        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, channel_id: str) -> Optional[PlatformChannel]:
        model = (
            self.db.query(PlatformChannelModel)
            .filter(PlatformChannelModel.id == channel_id)
            .first()
        )
        return self._to_domain(model) if model else None

    def get_by_connection_external(
        self, connection_id: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        model = (
            self.db.query(PlatformChannelModel)
            .filter(
                PlatformChannelModel.platform_connection_id == connection_id,
                PlatformChannelModel.channel_external_id == channel_external_id,
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def find_by_external_id(
        self, platform: str, channel_external_id: str
    ) -> Optional[PlatformChannel]:
        model = (
            self.db.query(PlatformChannelModel)
            .filter(
                PlatformChannelModel.platform == platform,
                PlatformChannelModel.channel_external_id == channel_external_id,
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def list_by_connection(self, connection_id: str) -> List[PlatformChannel]:
        models = (
            self.db.query(PlatformChannelModel)
            .filter(PlatformChannelModel.platform_connection_id == connection_id)
            .order_by(PlatformChannelModel.is_primary.desc(), PlatformChannelModel.channel_name.asc())
            .all()
        )
        return [self._to_domain(model) for model in models]

    def list_enabled(self, platform: Optional[str] = None) -> List[PlatformChannel]:
        query = self.db.query(PlatformChannelModel).filter(
            PlatformChannelModel.is_enabled.is_(True)
        )
        if platform:
            query = query.filter(PlatformChannelModel.platform == platform)
        models = query.order_by(
            PlatformChannelModel.platform.asc(),
            PlatformChannelModel.is_primary.desc(),
            PlatformChannelModel.channel_name.asc(),
        ).all()
        return [self._to_domain(model) for model in models]

    def set_enabled(self, channel_id: str, enabled: bool) -> Optional[PlatformChannel]:
        model = (
            self.db.query(PlatformChannelModel)
            .filter(PlatformChannelModel.id == channel_id)
            .first()
        )
        if not model:
            return None
        model.is_enabled = enabled
        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def count(self, enabled_only: bool = True) -> int:
        query = self.db.query(PlatformChannelModel)
        if enabled_only:
            query = query.filter(PlatformChannelModel.is_enabled.is_(True))
        return query.count()

    def delete(self, channel_id: str) -> bool:
        model = (
            self.db.query(PlatformChannelModel)
            .filter(PlatformChannelModel.id == channel_id)
            .first()
        )
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
