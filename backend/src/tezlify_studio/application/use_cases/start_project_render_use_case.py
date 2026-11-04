import logging
import os
import shutil
import threading
import uuid
from typing import Optional

from tezlify_studio.application.ports.render_job_repository_port import RenderJobRepositoryPort
from tezlify_studio.application.ports.studio_project_repository_port import StudioProjectRepositoryPort
from tezlify_studio.application.dto.render_dto import RenderJobDTO, StartRenderRequestDTO
from tezlify_studio.application.use_cases.execute_render_job_use_case import (
    ExecuteRenderJobUseCase,
    cancel_render_process,
)
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus, StudioProjectStatus
from tezlify_studio.domain.exceptions.studio_exceptions import (
    StudioProjectNotFoundException,
    InvalidSceneGraphException,
    InvalidRenderStateException,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active render thread registry (for graceful shutdown)
# ---------------------------------------------------------------------------
_ACTIVE_RENDER_THREADS: dict[str, threading.Thread] = {}
_THREADS_LOCK = threading.Lock()
_SHUTDOWN_REQUESTED = threading.Event()


def register_render_thread(job_id: str, thread: threading.Thread) -> None:
    with _THREADS_LOCK:
        _ACTIVE_RENDER_THREADS[job_id] = thread


def deregister_render_thread(job_id: str) -> None:
    with _THREADS_LOCK:
        _ACTIVE_RENDER_THREADS.pop(job_id, None)


def request_shutdown() -> None:
    """Signal all render workers to stop as soon as possible."""
    _SHUTDOWN_REQUESTED.set()


def is_shutdown_requested() -> bool:
    return _SHUTDOWN_REQUESTED.is_set()


def shutdown_render_workers(grace_seconds: float = 30.0) -> None:
    """Cancel running render processes and join worker threads with a timeout.

    Does not block forever: threads that do not finish within ``grace_seconds``
    are left running, but the wait is capped so shutdown is predictable.
    """
    request_shutdown()

    # Terminate every known subprocess so workers unblock from proc.wait().
    with _THREADS_LOCK:
        job_ids = list(_ACTIVE_RENDER_THREADS.keys())

    for job_id in job_ids:
        try:
            cancel_render_process(job_id)
        except Exception:
            logger.warning(f"Failed to cancel render process {job_id} during shutdown", exc_info=True)

    import time as _time

    start = _time.monotonic()
    while _time.monotonic() - start < grace_seconds:
        with _THREADS_LOCK:
            remaining = [t for t in _ACTIVE_RENDER_THREADS.values() if t.is_alive()]
        if not remaining:
            return
        for thread in remaining:
            thread.join(timeout=min(1.0, grace_seconds - (_time.monotonic() - start)))
        if _time.monotonic() - start >= grace_seconds:
            break

    with _THREADS_LOCK:
        still_alive = [t for t in _ACTIVE_RENDER_THREADS.values() if t.is_alive()]
    if still_alive:
        logger.warning(
            f"{len(still_alive)} render thread(s) did not finish within {grace_seconds}s grace period"
        )


class StartProjectRenderUseCase:
    def __init__(
        self,
        project_repo: StudioProjectRepositoryPort,
        render_job_repo: RenderJobRepositoryPort,
        execute_worker: ExecuteRenderJobUseCase,
    ):
        self.project_repo = project_repo
        self.render_job_repo = render_job_repo
        self.execute_worker = execute_worker

        # Minimum free disk space (bytes) required before starting a render.
        # Defaults to 1 GB; overridable via settings if desired.
        self.min_free_disk_bytes = 1024 * 1024 * 1024

    def _check_disk_space(self, base_dir: str) -> None:
        """Raise InvalidRenderStateException if there is not enough disk space."""
        try:
            usage = shutil.disk_usage(base_dir)
        except OSError as exc:
            logger.warning(f"Could not check disk usage for {base_dir}: {exc}")
            return
        if usage.free < self.min_free_disk_bytes:
            free_gb = round(usage.free / (1024 * 1024 * 1024), 2)
            raise InvalidRenderStateException(
                f"Yetersiz disk alani: {free_gb} GB bos, en az 1.00 GB gerekli. "
                f"Lutfen bos alan olusturun ve yeniden deneyin."
            )

    def execute(self, request: StartRenderRequestDTO) -> RenderJobDTO:
        if is_shutdown_requested():
            raise InvalidRenderStateException(
                "Uygulama kapaniyor, yeni render baslatilamaz."
            )

        project = self.project_repo.get_by_id(request.project_id)
        if not project:
            raise StudioProjectNotFoundException(request.project_id)

        if not project.scene_graph:
            raise InvalidSceneGraphException("Proje için henüz bir SceneGraph oluşturulmamış.")

        if not project.scene_graph.scenes:
            raise InvalidSceneGraphException("SceneGraph içinde en az 1 sahne bulunmalıdır.")

        # Check existing running jobs for this project
        existing_jobs = self.render_job_repo.list_by_project_id(request.project_id, limit=5)
        for ej in existing_jobs:
            if ej.status == RenderJobStatus.RUNNING:
                raise InvalidRenderStateException(
                    f"Bu proje için devam eden aktif bir render görevi var (ID: {ej.id}). Lütfen tamamlanmasını bekleyin."
                )

        # Disk space guard before dispatching the worker.
        base_data_dir = getattr(self.execute_worker.animation_engine, "base_projects_dir", "data/studio_projects")
        self._check_disk_space(base_data_dir)

        job_id = f"render_{uuid.uuid4().hex[:12]}"
        job = RenderJob(
            id=job_id,
            project_id=request.project_id,
            status=RenderJobStatus.PENDING,
            progress_percent=0.0,
            current_step="Pending render dispatch",
        )
        saved_job = self.render_job_repo.save(job)

        project.transition_to(StudioProjectStatus.RENDER_QUEUED)
        self.project_repo.save(project)

        # Launch background render worker thread (non-daemon so shutdown can wait).
        def _target():
            try:
                self.execute_worker.execute(
                    saved_job.id, request.project_id, request.engine_override, request.synthesize_voices
                )
            finally:
                deregister_render_thread(saved_job.id)

        worker_thread = threading.Thread(
            target=_target,
            daemon=False,
            name=f"RenderWorker-{saved_job.id}",
        )
        register_render_thread(saved_job.id, worker_thread)
        worker_thread.start()

        return RenderJobDTO.from_entity(saved_job)
