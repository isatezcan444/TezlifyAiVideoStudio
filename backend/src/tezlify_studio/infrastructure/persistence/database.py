from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.infrastructure.persistence.models.media_models import Base
# Import publish & schedule models so they are registered on Base.metadata
import tezlify_studio.infrastructure.persistence.models.publish_models  # noqa: F401
import tezlify_studio.infrastructure.persistence.models.schedule_models  # noqa: F401
import tezlify_studio.infrastructure.persistence.models.studio_models  # noqa: F401

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

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

