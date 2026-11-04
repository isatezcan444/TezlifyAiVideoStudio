from abc import ABC, abstractmethod
from typing import Optional
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph

class StoryPlannerPort(ABC):
    @abstractmethod
    def plan_story(
        self,
        prompt: str,
        target_duration_seconds: Optional[float] = None,
        aspect_ratio: Optional[str] = "16:9",
        genre: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SceneGraph:
        """
        Generates a validated SceneGraph from a user text prompt.
        """
        pass
