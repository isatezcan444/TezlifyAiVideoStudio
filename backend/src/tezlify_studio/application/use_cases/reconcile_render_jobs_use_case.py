"""Render job startup reconciliation (Stage 5.0.1).

On application startup, any RenderJob left in ``RUNNING`` state from a
previous (crashed or restarted) server process cannot have an active worker
anymore. This use case marks those stale jobs as ``FAILED`` so that new
renders can be started for the affected projects.

The reconciliation is idempotent: COMPLETED, FAILED and CANCELLED jobs are
never touched, and running the reconciliation twice is a no-op after the
first pass.
"""

from __future__ import annotations

from typing import Optional

from tezlify_studio.application.ports.render_job_repository_port import (
    RenderJobRepositoryPort,
)
from tezlify_studio.domain.enums.studio_status import RenderJobStatus, StudioProjectStatus
from tezlify_studio.domain.exceptions.studio_exceptions import StudioProjectNotFoundException


class ReconcileRenderJobsUseCase:
    """Marks stale RUNNING render jobs as FAILED so projects are unblocked."""

    def __init__(
        self,
        render_job_repo: RenderJobRepositoryPort,
        project_repo: Optional[object] = None,
    ):
        self.render_job_repo = render_job_repo
        self.project_repo = project_repo

    def execute(self) -> int:
        """Reconcile all stale RUNNING render jobs.

        Returns the number of jobs that were transitioned to FAILED.
        """
        # NOTE: RenderJobRepositoryPort does not expose a status-filtered list
        # in all implementations, so we fetch pending/running candidates via
        # list_jobs with a status filter when available and fall back to a full
        # scan otherwise.
        try:
            candidates = self.render_job_repo.list_jobs(
                limit=1000, offset=0, status=RenderJobStatus.RUNNING
            )
        except TypeError:
            candidates = [
                j
                for j in self.render_job_repo.list_jobs(limit=1000, offset=0)
                if j.status == RenderJobStatus.RUNNING
            ]

        reconciled = 0
        for job in candidates:
            if job.status != RenderJobStatus.RUNNING:
                # Idempotent: already reconciled by a previous pass.
                continue

            job.fail(
                "Sunucu yeniden ba\u011flat\u0131ld\u0131\u011f\u0131 i\u00e7in render i\u015flemi tamamlanamam\u0131\u015f. L\u00fctfen yeniden deneyin."
            )
            self.render_job_repo.save(job)

            # Transition the owning project back so it can be re-rendered.
            if self.project_repo is not None:
                try:
                    project = self.project_repo.get_by_id(job.project_id)
                    if project is not None and project.status in (
                        StudioProjectStatus.RENDERING,
                        StudioProjectStatus.RENDER_QUEUED,
                    ):
                        project.transition_to(StudioProjectStatus.FAILED)
                        self.project_repo.save(project)
                except StudioProjectNotFoundException:
                    pass

            reconciled += 1

        return reconciled
