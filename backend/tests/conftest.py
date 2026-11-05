"""Test isolation for the whole backend suite.

Without this file every integration test that does `TestClient(app)` at import
time runs `create_app()`, which calls `init_db()` and the startup reconciliations
against the *user's* SQLite database, and every render test writes into the
user's real `data/studio_projects`. That is how the production database ended up
with dozens of `pending` jobs named after test fixtures.

The rule enforced here: `DATA_DIR` points at a scratch tree before anything under
`tezlify_studio` is imported. `settings` is a module-level singleton
(`infrastructure/configuration/settings.py`), and `database.py` binds its engine
at import time, so setting the variable any later than this file would be too
late. Environment variables outrank `.env` in pydantic-settings, which matters
because this machine's `.env` does set `DATA_DIR`.

Character/prop/background `.blend` assets are copied into the scratch tree
instead of being regenerated: they are inputs, they are ~16 MB, and rebuilding
them would make the Blender tests depend on a working Blender build step.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REAL_DATA_DIR = os.path.join(_REPO_ROOT, "data")

# A scratch tree per pytest session, deliberately outside the repository so a
# stray relative path cannot resolve back into the user's data directory.
_ISOLATED_DATA_DIR = tempfile.mkdtemp(prefix="tezlify-test-data-")

os.environ["DATA_DIR"] = _ISOLATED_DATA_DIR
# Force the deterministic, offline behaviour the suite was never able to rely on
# while it shared the user's environment: no live voice API, no scheduler.
os.environ.setdefault("ELEVENLABS_API_KEY", "")
os.environ["TEZLIFY_TEST_ENV"] = "1"
os.environ["SCHEDULER_ENABLED"] = "false"

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_SRC = os.path.join(_REPO_ROOT, "backend", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _copy_builtin_assets() -> None:
    """Give the scratch tree the same readable asset library the app has."""
    src = os.path.join(_REAL_DATA_DIR, "studio_assets")
    if not os.path.isdir(src):
        return
    dst = os.path.join(_ISOLATED_DATA_DIR, "studio_assets")
    if os.path.isdir(dst):
        return
    shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns("__pycache__"))


def pytest_sessionstart(session) -> None:  # noqa: ARG001
    _copy_builtin_assets()
    from tezlify_studio.infrastructure.configuration.settings import settings

    resolved = settings.resolved_data_dir
    if resolved != _ISOLATED_DATA_DIR:
        raise RuntimeError(
            f"test isolation failed: DATA_DIR resolved to {resolved!r}, "
            f"expected {_ISOLATED_DATA_DIR!r}"
        )
    if resolved == os.path.abspath(_REAL_DATA_DIR):
        raise RuntimeError("refusing to run tests against the user's real data directory")
    # Some tests open the global SessionLocal directly instead of going through
    # the API. On the scratch database nothing has created the schema yet, and a
    # test that silently depended on the user's tables is exactly what this file
    # exists to stop.
    from tezlify_studio.infrastructure.persistence.database import init_db

    init_db()
    print(f"\n[tezlify tests] isolated DATA_DIR = {resolved}")


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    shutil.rmtree(_ISOLATED_DATA_DIR, ignore_errors=True)
