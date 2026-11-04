from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, Float
from tezlify_studio.infrastructure.persistence.models.media_models import Base

class StudioProjectModel(Base):
    __tablename__ = "studio_projects"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default="draft", nullable=False)
    scene_graph_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class CharacterModel(Base):
    __tablename__ = "characters"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    gender = Column(String(32), default="neutral", nullable=False)
    palette_json = Column(Text, nullable=False)
    hair_style = Column(String(64), default="short_parted", nullable=False)
    eye_style = Column(String(64), default="round", nullable=False)
    clothing_style = Column(String(64), default="casual", nullable=False)
    voice_id = Column(String(64), default="", nullable=False)
    default_expression = Column(String(32), default="neutral", nullable=False)
    default_pose = Column(String(32), default="standing", nullable=False)
    proportions_json = Column(Text, nullable=False)
    blend_file_path = Column(String(512), nullable=True)
    thumbnail_path = Column(String(512), nullable=True)
    is_builtin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class StudioAssetModel(Base):
    __tablename__ = "studio_assets"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False, index=True)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)
    asset_format = Column(String(32), default="blend", nullable=False)
    thumbnail_path = Column(String(512), nullable=True)
    version = Column(String(16), default="1.0", nullable=False)
    tags_json = Column(Text, default="[]", nullable=False)
    is_builtin = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class RenderJobModel(Base):
    __tablename__ = "render_jobs"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False, index=True)
    progress_percent = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(255), default="Pending", nullable=False)
    output_video_path = Column(String(512), nullable=True)
    output_metadata_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
