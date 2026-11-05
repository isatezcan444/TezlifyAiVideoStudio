from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from tezlify_studio.infrastructure.persistence.models.media_models import Base


class PlatformConnectionModel(Base):
    __tablename__ = "platform_connections"
    __table_args__ = (
        UniqueConstraint("platform", "account_external_id", name="uq_platform_connection_account"),
    )

    id = Column(String(64), primary_key=True, index=True)
    platform = Column(String(32), index=True, nullable=False)
    account_external_id = Column(String(255), index=True, nullable=False)
    account_display_name = Column(String(255), nullable=False)
    connection_status = Column(String(32), index=True, nullable=False, default="active")
    token_reference = Column(String(255), unique=True, nullable=False)
    granted_scopes_json = Column(Text, default="[]", nullable=False)
    connected_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_refreshed_at = Column(DateTime, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    channels = relationship(
        "PlatformChannelModel",
        back_populates="connection",
        cascade="all, delete-orphan",
    )


class PlatformChannelModel(Base):
    __tablename__ = "platform_channels"
    __table_args__ = (
        UniqueConstraint(
            "platform_connection_id",
            "channel_external_id",
            name="uq_platform_channel_per_connection",
        ),
    )

    id = Column(String(64), primary_key=True, index=True)
    platform_connection_id = Column(
        String(64),
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    platform = Column(String(32), index=True, nullable=False)
    channel_external_id = Column(String(128), index=True, nullable=False)
    channel_name = Column(String(255), nullable=False)
    channel_handle = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)
    description = Column(Text, default="", nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    subscriber_count = Column(Integer, nullable=True)
    uploads_playlist_id = Column(String(128), nullable=True)
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    connection = relationship("PlatformConnectionModel", back_populates="channels")


class UserChannelPreferenceModel(Base):
    __tablename__ = "user_channel_preferences"

    id = Column(String(32), primary_key=True, default="default")
    active_channel_id = Column(String(64), nullable=True)
    default_platform = Column(String(32), default="youtube", nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
