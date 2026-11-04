from abc import ABC, abstractmethod
from typing import Optional

from tezlify_studio.domain.value_objects.video_composition import VideoComposition


class CompositionRepositoryPort(ABC):
    @abstractmethod
    def save(self, composition: VideoComposition) -> VideoComposition:
        """Creates or updates the composition for a project."""

    @abstractmethod
    def get_by_project_id(self, project_id: str) -> Optional[VideoComposition]:
        """Returns the saved composition for a project, if any."""

    @abstractmethod
    def delete_by_project_id(self, project_id: str) -> bool:
        """Deletes the saved composition for a project."""
