from abc import ABC, abstractmethod
from typing import Callable, Optional
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata

class BlenderAnimationEnginePort(ABC):
    @abstractmethod
    def render_animation(
        self,
        scene_graph: SceneGraph,
        project_id: str,
        job_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        engine_override: Optional[str] = None,
    ) -> RenderOutputMetadata:
        """Renders the given scene graph to a playable, validated MP4 video."""
        pass
