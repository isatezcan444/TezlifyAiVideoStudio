import logging
import os
import shutil
from typing import Optional

from tezlify_studio.application.ports.studio_project_repository_port import (
    StudioProjectRepositoryPort,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    StudioProjectNotFoundException,
)
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.infrastructure.configuration.settings import settings

logger = logging.getLogger(__name__)

# Base directory that holds per-project render/audio/frame output.
# Resolved once at import time so path-containment checks are consistent.
_PROJECTS_BASE_DIR = os.path.abspath(
    os.path.join(settings.resolved_data_dir, "studio_projects")
)


def _is_path_within_base(path: str, base: str) -> bool:
    """Return True if ``path`` resolves to a location under ``base``.

    Uses realpath to resolve symlinks and ``..`` segments before comparing,
    preventing symlink-based traversal out of the projects base directory.
    """
    try:
        real_path = os.path.realpath(path)
        real_base = os.path.realpath(base)
        return real_path == real_base or real_path.startswith(real_base + os.sep)
    except Exception:
        return False


class DeleteStudioProjectUseCase:
    def __init__(self, repo: StudioProjectRepositoryPort):
        self.repo = repo

    def execute(self, project_id: str, archive_only: bool = False) -> bool:
        project = self.repo.get_by_id(project_id)
        if not project:
            raise StudioProjectNotFoundException(project_id)

        if archive_only:
            project.transition_to(StudioProjectStatus.ARCHIVED)
            self.repo.save(project)
            return True

        # Determine the per-project output directory before deleting the DB row,
        # so we can clean up render/audio/frame artifacts belonging only to this
        # project. Guard against path traversal/symlink escape.
        project_dir = os.path.abspath(os.path.join(_PROJECTS_BASE_DIR, project_id))
        if not _is_path_within_base(project_dir, _PROJECTS_BASE_DIR):
            logger.error(
                f"Refusing to delete project {project_id}: resolved path escapes projects base directory."
            )
            raise StudioProjectNotFoundException(project_id)

        deleted = self.repo.delete(project_id)

        if deleted and os.path.isdir(project_dir):
            try:
                shutil.rmtree(project_dir)
                logger.info(f"Deleted project directory {project_dir}")
            except OSError as exc:
                # Log but do not fail the request: the DB row is already gone.
                # A leftover directory is preferable to a 500 on delete.
                logger.warning(
                    f"Failed to delete project directory {project_dir}: {exc}"
                )

        return deleted
