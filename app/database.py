"""SQLAlchemy engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from time import sleep

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

_SQLITE_SCHEMA_RACE_MESSAGE = "already exists"
_SQLITE_SCHEMA_CREATE_ATTEMPTS = 3


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
    engine_kwargs: dict = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if settings.database_url in {"sqlite:///:memory:", "sqlite://"}:
            engine_kwargs["poolclass"] = StaticPool
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
        **engine_kwargs,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Importing models here registers them with `Base.metadata`.
    from app import models  # noqa: F401

    for attempt in range(_SQLITE_SCHEMA_CREATE_ATTEMPTS):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError as exc:
            if not engine.url.get_backend_name().startswith("sqlite") or (
                _SQLITE_SCHEMA_RACE_MESSAGE not in str(exc).lower()
            ):
                raise
            if attempt == _SQLITE_SCHEMA_CREATE_ATTEMPTS - 1:
                raise

            # Two SQLite-backed app instances can start against an empty
            # database at the same time. SQLAlchemy's check-then-create can
            # race, so retry after the other process has created the table that
            # caused the failure.
            sleep(0.05)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
