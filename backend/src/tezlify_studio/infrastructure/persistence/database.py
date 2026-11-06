from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.models.media_models import Base
# Import publish & schedule models so they are registered on Base.metadata.
# Legacy video-generation tables (studio_projects, characters, studio_assets,
# video_compositions, render_jobs) are intentionally NOT registered: their data
# stays untouched in existing databases, but no runtime code creates or reads them.
import tezlify_studio.infrastructure.persistence.models.publish_models  # noqa: F401
import tezlify_studio.infrastructure.persistence.models.schedule_models  # noqa: F401
import tezlify_studio.infrastructure.persistence.models.connection_models  # noqa: F401

# Create SQLite engine with WAL mode and foreign key constraints enabled
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Additive column backfills for databases created before these fields existed.
# SQLite cannot add columns through create_all, and there is no migration
# framework in this project; ADD COLUMN is metadata-only and leaves row data
# untouched.
_COLUMN_BACKFILLS = {
    "publish_records": {
        "playlist_id": "VARCHAR(64)",
    },
    "scheduled_publishes": {
        "category_id": "VARCHAR(32) DEFAULT '22'",
        "thumbnail_path": "TEXT",
        "playlist_id": "VARCHAR(64)",
    },
}


def _ensure_columns() -> None:
    with engine.begin() as conn:
        for table, columns in _COLUMN_BACKFILLS.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:
                continue
            for name, ddl in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"
                    )


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_columns()

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

