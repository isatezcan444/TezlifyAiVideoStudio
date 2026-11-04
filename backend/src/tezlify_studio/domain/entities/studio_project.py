from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph

@dataclass
class StudioProject:
    id: str
    title: str
    description: str = ""
    status: StudioProjectStatus = StudioProjectStatus.DRAFT
    scene_graph: Optional[SceneGraph] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update_metadata(self, title: Optional[str] = None, description: Optional[str] = None) -> None:
        if title is not None:
            clean = title.strip()
            if not clean:
                raise ValueError("Proje başlığı boş olamaz.")
            self.title = clean
            if self.scene_graph:
                self.scene_graph.title = clean
        if description is not None:
            self.description = description
            if self.scene_graph:
                self.scene_graph.description = description
        self.updated_at = datetime.now(timezone.utc)

    def update_scene_graph(self, scene_graph: SceneGraph) -> None:
        self.scene_graph = scene_graph
        self.title = scene_graph.title
        self.description = scene_graph.description
        self.updated_at = datetime.now(timezone.utc)

    def transition_to(self, new_status: StudioProjectStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
