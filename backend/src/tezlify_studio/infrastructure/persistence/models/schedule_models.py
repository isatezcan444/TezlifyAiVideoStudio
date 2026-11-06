import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from tezlify_studio.infrastructure.persistence.models.media_models import Base

class ScheduledPublishModel(Base):
    __tablename__ = "scheduled_publishes"

    id = Column(String(64), primary_key=True, index=True)
    media_asset_id = Column(
        String(64),
        ForeignKey("media_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    social_account_id = Column(
        String(64),
        ForeignKey("social_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel_id = Column(
        String(64),
        ForeignKey("platform_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform_connection_id = Column(
        String(64),
        ForeignKey("platform_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel_attribution = Column(String(32), default="unresolved", nullable=False)
    platform = Column(String(32), default="youtube", index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    tags_json = Column(Text, default="[]", nullable=False)
    category_id = Column(String(32), default="22", nullable=False)
    privacy_status = Column(String(32), default="private", nullable=False)
    thumbnail_path = Column(Text, nullable=True)
    playlist_id = Column(String(64), nullable=True)
    scheduled_at_utc = Column(DateTime, nullable=False, index=True)
    timezone = Column(String(64), default="UTC", nullable=False)
    status = Column(String(32), default="scheduled", index=True, nullable=False)
    publish_record_id = Column(
        String(64),
        ForeignKey("publish_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_error_code = Column(String(64), nullable=True)
    last_error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    media_asset = relationship("MediaAssetModel")
    social_account = relationship("SocialAccountModel")
    publish_record = relationship("PublishRecordModel")

    @property
    def tags_list(self) -> list[str]:
        try:
            return json.loads(self.tags_json) if self.tags_json else []
        except Exception:
            return []

    @tags_list.setter
    def tags_list(self, val: list[str]) -> None:
        self.tags_json = json.dumps(val or [])
