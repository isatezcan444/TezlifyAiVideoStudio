import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from tezlify_studio.infrastructure.persistence.models.media_models import Base

class SocialAccountModel(Base):
    __tablename__ = "social_accounts"

    id = Column(String(64), primary_key=True, index=True)
    platform = Column(String(32), index=True, nullable=False)
    account_name = Column(String(255), nullable=False)
    channel_id = Column(String(128), index=True, nullable=False)
    channel_avatar_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class PublishRecordModel(Base):
    __tablename__ = "publish_records"

    id = Column(String(64), primary_key=True, index=True)
    media_asset_id = Column(String(64), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(32), default="youtube", index=True, nullable=False)
    external_video_id = Column(String(128), index=True, nullable=True)
    external_video_url = Column(Text, nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    tags_json = Column(Text, default="[]", nullable=False)
    category_id = Column(String(32), default="22", nullable=False)
    privacy_status = Column(String(32), default="private", nullable=False)
    status = Column(String(32), default="pending", index=True, nullable=False)
    progress_percentage = Column(Integer, default=0, nullable=False)
    uploaded_bytes = Column(Integer, default=0, nullable=False)
    total_bytes = Column(Integer, default=0, nullable=False)
    upload_session_uri = Column(Text, nullable=True)
    thumbnail_path = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    published_at = Column(DateTime, nullable=True)

    session = relationship("UploadSessionModel", back_populates="publish_record", uselist=False, cascade="all, delete-orphan")

    @property
    def tags_list(self) -> list[str]:
        try:
            return json.loads(self.tags_json) if self.tags_json else []
        except Exception:
            return []

    @tags_list.setter
    def tags_list(self, val: list[str]) -> None:
        self.tags_json = json.dumps(val or [])

class UploadSessionModel(Base):
    __tablename__ = "upload_sessions"

    id = Column(String(64), primary_key=True, index=True)
    publish_record_id = Column(String(64), ForeignKey("publish_records.id", ondelete="CASCADE"), unique=True, nullable=False)
    session_uri = Column(Text, nullable=False)
    last_byte = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    publish_record = relationship("PublishRecordModel", back_populates="session")
