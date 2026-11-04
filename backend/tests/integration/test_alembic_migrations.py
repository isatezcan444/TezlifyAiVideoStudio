import os
import subprocess
import sqlite3
import pytest

def test_alembic_migration_chain_isolated(tmp_path):
    test_db_path = str(tmp_path / "isolated_test_migration.db")
    alembic_bin = os.path.abspath(".venv/bin/alembic")
    
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    env["PYTHONPATH"] = os.path.abspath("backend/src")

    # 1. Upgrade from clean empty DB to head
    res_up = subprocess.run([alembic_bin, "upgrade", "head"], cwd="backend", env=env, capture_output=True, text=True)
    assert res_up.returncode == 0, f"Alembic upgrade failed: {res_up.stderr}"

    con = sqlite3.connect(test_db_path)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    con.close()

    assert "characters" in tables
    assert "studio_assets" in tables
    assert "studio_projects" in tables
    assert "scheduled_publishes" in tables
    assert "publish_records" in tables
    assert "media_assets" in tables

    # 2. Downgrade to base
    res_down = subprocess.run([alembic_bin, "downgrade", "base"], cwd="backend", env=env, capture_output=True, text=True)
    assert res_down.returncode == 0, f"Alembic downgrade failed: {res_down.stderr}"

    con = sqlite3.connect(test_db_path)
    cur = con.cursor()
    tables_after = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall() if r[0] != "alembic_version"]
    con.close()
    assert len(tables_after) == 0

    # 3. Upgrade back to head
    res_up2 = subprocess.run([alembic_bin, "upgrade", "head"], cwd="backend", env=env, capture_output=True, text=True)
    assert res_up2.returncode == 0, f"Alembic re-upgrade failed: {res_up2.stderr}"
