from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime
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
