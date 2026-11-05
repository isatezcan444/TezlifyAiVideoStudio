from datetime import timezone

from sqlalchemy.orm import Session

from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.domain.entities.channel_selection import ChannelSelection
from tezlify_studio.infrastructure.persistence.models.connection_models import (
    UserChannelPreferenceModel,
)


class ChannelSelectionRepositoryImpl(ChannelSelectionRepositoryPort):
    ROW_ID = "default"

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> ChannelSelection:
        model = (
            self.db.query(UserChannelPreferenceModel)
            .filter(UserChannelPreferenceModel.id == self.ROW_ID)
            .first()
        )
        if not model:
            return ChannelSelection()
        updated_at = model.updated_at
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return ChannelSelection(
            id=model.id,
            active_channel_id=model.active_channel_id,
            default_platform=model.default_platform or "youtube",
            updated_at=updated_at,
        )

    def save(self, selection: ChannelSelection) -> ChannelSelection:
        model = (
            self.db.query(UserChannelPreferenceModel)
            .filter(UserChannelPreferenceModel.id == self.ROW_ID)
            .first()
        )
        if not model:
            model = UserChannelPreferenceModel(
                id=self.ROW_ID,
                active_channel_id=selection.active_channel_id,
                default_platform=selection.default_platform,
                updated_at=selection.updated_at,
            )
            self.db.add(model)
        else:
            model.active_channel_id = selection.active_channel_id
            model.default_platform = selection.default_platform
            model.updated_at = selection.updated_at
        self.db.commit()
        self.db.refresh(model)
        return self.get()
