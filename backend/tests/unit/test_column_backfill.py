from sqlalchemy import create_engine

import tezlify_studio.infrastructure.persistence.database as database


def test_ensure_columns_adds_missing_columns_without_touching_rows(tmp_path, monkeypatch):
    legacy_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{legacy_path}")
    with legacy_engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE publish_records (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE scheduled_publishes (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO publish_records (id) VALUES ('legacy-row')")

    monkeypatch.setattr(database, "engine", legacy_engine)

    database._ensure_columns()
    database._ensure_columns()

    with legacy_engine.begin() as conn:
        publish_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(publish_records)")
        }
        schedule_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(scheduled_publishes)")
        }
        row = conn.exec_driver_sql(
            "SELECT id, playlist_id FROM publish_records"
        ).fetchone()

    assert "playlist_id" in publish_columns
    assert {"category_id", "thumbnail_path", "playlist_id"} <= schedule_columns
    assert row[0] == "legacy-row"
    assert row[1] is None
