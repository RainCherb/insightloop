"""SQLAlchemy engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _resolve_sqlite_path(url: str) -> None:
    """Make sure the parent directory of a sqlite file URL exists."""
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            parent = Path(path).expanduser().resolve().parent
            parent.mkdir(parents=True, exist_ok=True)


def _build_engine() -> Engine:
    settings = get_settings()
    _resolve_sqlite_path(settings.database_url)
    connect_args: dict = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Importing models here registers them with `Base.metadata`.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
