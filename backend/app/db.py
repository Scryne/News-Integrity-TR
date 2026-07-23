"""Database engine, session factory, and connect-time SQLite pragmas.

ADR-003: sync SQLAlchemy 2.0 over SQLite. Every connection gets WAL,
foreign_keys=ON and busy_timeout via a connect-event listener (ARCHITECTURE §5).
This module owns the engine and the declarative Base only; ORM models live in
app.models and schema migrations in alembic/. No query or write logic here —
that is T4-T6.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model (SQLAlchemy 2.0 style)."""


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """Apply the ARCHITECTURE §5 pragmas on every new SQLite connection.

    Registered process-wide (we only ever open SQLite engines), so Alembic's
    own engine picks it up too once this module is imported. WAL is
    database-level and persists once set; foreign_keys and busy_timeout are
    per-connection and must be re-applied on each connect.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def build_engine(settings: Settings | None = None) -> Engine:
    """Create the SQLite engine, ensuring the data dir exists first."""
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{settings.db_path.as_posix()}", echo=False)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
