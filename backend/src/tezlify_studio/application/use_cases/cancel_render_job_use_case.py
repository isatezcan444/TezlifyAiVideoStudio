"""Render job cancellation use case (Stage 5.0.1).

Allows cancelling a PENDING or RUNNING render job. For RUNNING jobs the
underlying Blender/FFmpeg subprocess is terminated. The job is transitioned
to CANCELLED and the owning project is marked FAILED so it can be re-rendered.

The operation is idempotent: cancelling an already CANCELLED, COMPLETED or
FAILED job is a no-op that returns the current job state without error.
"""

from __future__ import annotations

from tezlify_studio.application.ports.render_job_repository_port import (
    RenderJobRepositoryPort,
)
from tezlify_studio.application.use_cases.execute_render_job_use_case import (
    cancel_render_process,
    is_job_cancelled,
)
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import (
    RenderJobStatus,
    StudioProjectStatus,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    RenderJobNotFoundException,
    StudioProjectNotFoundException,
)


class CancelRenderJobUseCase:
    def __init__(
        self,
        render_job_repo: RenderJobRepositoryPort,
        project_repo: object,
    ):
        self.render_job_repo = render_job_repo
        self.project_repo = project_repo

    def execute(self, job_id: str) -> RenderJob:
        """Cancel a render job.

        Returns the (possibly already cancelled/completed/failed) job.
        Raises RenderJobNotFoundException when the job does not exist.
        """
        job = self.render_job_repo.get_by_id(job_id)
        if job is None:
            raise RenderJobNotFoundException(job_id)

        # Idempotent: terminal states are not changed.
        if job.status in (
            RenderJobStatus.COMPLETED,
            RenderJobStatus.FAILED,
            RenderJobStatus.CANCELLED,
        ):
            return job

        if job.status == RenderJobStatus.PENDING:
            # Nothing running to terminate; just mark cancelled.
            job.cancel()
            self.render_job_repo.save(job)
            self._fail_project(job.project_id)
            return job

        if job.status == RenderJobStatus.RUNNING:
            # Terminate the underlying subprocess (Blender/FFmpeg) if one is
            # registered for this job. The worker will observe the cancelled
            # flag and record CANCELLED instead of FAILED.
            cancel_render_process(job_id)

            # If the worker already finished between our check and now, the
            # process may no longer be registered; still mark cancelled.
            job.cancel()
            self.render_job_repo.save(job)
            self._fail_project(job.project_id)
            return job

        # Any other status: leave untouched.
        return job

    def _fail_project(self, project_id: str) -> None:
        """Mark the owning project FAILED so it is eligible for re-render."""
        try:
            project = self.project_repo.get_by_id(project_id)
        except StudioProjectNotFoundException:
            return
        if project is None:
            return
        if project.status in (
            StudioProjectStatus.RENDERING,
            StudioProjectStatus.RENDER_QUEUED,
        ):
            project.transition_to(StudioProjectStatus.FAILED)
            self.project_repo.save(project)
