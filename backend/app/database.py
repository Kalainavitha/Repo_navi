import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = BACKEND_DIR / "genplan.db"
DATABASE_URL = os.getenv("DATABASE_URL")
database_url = make_url(DATABASE_URL) if DATABASE_URL else URL.create("sqlite", database=str(DEFAULT_DATABASE_PATH))

if database_url.drivername.startswith("sqlite") and database_url.database not in (None, ":memory:"):
    database_path = Path(database_url.database)
    if not database_path.is_absolute():
        database_path = BACKEND_DIR / database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = database_url.set(database=str(database_path))

connect_args = {"check_same_thread": False} if database_url.drivername.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, future=True)

if database_url.drivername.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
