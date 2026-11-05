"""Test isolation for the whole backend suite.

Without this file every integration test that does `TestClient(app)` at import
time runs `create_app()`, which calls `init_db()` and the startup reconciliations
against the *user's* SQLite database. That is how the production database ended up
with stray test rows written by earlier suites.

The rule enforced here: `DATA_DIR` points at a scratch tree before anything under
`tezlify_studio` is imported. `settings` is a module-level singleton
(`infrastructure/configuration/settings.py`), and `database.py` binds its engine
at import time, so setting the variable any later than this file would be too
late. Environment variables outrank `.env` in pydantic-settings, which matters
because this machine's `.env` does set `DATA_DIR`.
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
# No background scheduler and no live network client during tests.
os.environ["TEZLIFY_TEST_ENV"] = "1"
os.environ["SCHEDULER_ENABLED"] = "false"

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_SRC = os.path.join(_REPO_ROOT, "backend", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def pytest_sessionstart(session) -> None:  # noqa: ARG001
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
