"""Create and verify a timestamped SQLite backup before a schema migration.

Usage:
    .venv/bin/python scripts/backup_database.py
"""
import os
import sqlite3
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend", "src"))

from tezlify_studio.infrastructure.configuration.settings import settings  # noqa: E402


def main() -> int:
    db_path = settings.database_url.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return 1

    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = os.path.join(backup_dir, f"tezlify_studio_backup_{stamp}.db")

    source = sqlite3.connect(db_path)
    try:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                print(f"Backup integrity check failed: {integrity}")
                return 2
        finally:
            target.close()
    finally:
        source.close()

    print(backup_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
