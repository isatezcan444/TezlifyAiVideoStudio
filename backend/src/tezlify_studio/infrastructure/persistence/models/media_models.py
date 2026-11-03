from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    sha256_hash = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    thumbnail_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    metadata_relation = relationship(
        "VideoMetadataModel",
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined"
    )
    import_records = relationship(
        "ImportRecordModel",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="select"
    )

class VideoMetadataModel(Base):
    __tablename__ = "video_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_asset_id = Column(String(64), ForeignKey("media_assets.id", ondelete="CASCADE"), unique=True, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    video_codec = Column(String(64), nullable=True)
    audio_codec = Column(String(64), nullable=True)
    aspect_ratio = Column(String(32), nullable=True)
    probe_source = Column(String(32), default="ffprobe", nullable=False)

    asset = relationship("MediaAssetModel", back_populates="metadata_relation")

class ImportRecordModel(Base):
    __tablename__ = "import_records"

    id = Column(String(64), primary_key=True, index=True)
    media_asset_id = Column(String(64), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(64), default="manual_upload", nullable=False)
    status = Column(String(32), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    asset = relationship("MediaAssetModel", back_populates="import_records")
