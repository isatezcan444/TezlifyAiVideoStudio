from abc import ABC, abstractmethod
from typing import Optional, List
from tezlify_studio.domain.entities.studio_project import StudioProject
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus

class StudioProjectRepositoryPort(ABC):
    @abstractmethod
    def save(self, project: StudioProject) -> StudioProject:
        """Persists or updates a StudioProject entity."""
        pass

    @abstractmethod
    def get_by_id(self, project_id: str) -> Optional[StudioProject]:
        """Retrieves a StudioProject by its unique ID."""
        pass

    @abstractmethod
    def list_projects(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[StudioProjectStatus] = None,
    ) -> List[StudioProject]:
        """Lists StudioProjects with pagination and optional status filter."""
        pass

    @abstractmethod
    def count_projects(self, status: Optional[StudioProjectStatus] = None) -> int:
        """Counts total StudioProjects matching optional status filter."""
        pass

    @abstractmethod
    def delete(self, project_id: str) -> bool:
        """Deletes a StudioProject entity by ID. Returns True if deleted, False otherwise."""
        pass
