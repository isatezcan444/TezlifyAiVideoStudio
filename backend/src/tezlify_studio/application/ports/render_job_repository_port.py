from abc import ABC, abstractmethod
from typing import Optional, List
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus

class RenderJobRepositoryPort(ABC):
    @abstractmethod
    def save(self, job: RenderJob) -> RenderJob:
        """Persists or updates a RenderJob entity."""
        pass

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[RenderJob]:
        """Retrieves a RenderJob by its unique ID."""
        pass

    @abstractmethod
    def list_by_project_id(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RenderJob]:
        """Lists RenderJobs for a specific studio project, sorted by newest first."""
        pass

    @abstractmethod
    def list_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[RenderJobStatus] = None,
    ) -> List[RenderJob]:
        """Lists RenderJobs with optional status filter."""
        pass

    @abstractmethod
    def count_jobs(
        self,
        status: Optional[RenderJobStatus] = None,
    ) -> int:
        """Counts RenderJobs with an optional status filter."""
        pass

    @abstractmethod
    def delete(self, job_id: str) -> bool:
        """Deletes a RenderJob entity by ID. Returns True if deleted, False otherwise."""
        pass
