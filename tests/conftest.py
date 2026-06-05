"""Pytest fixtures: in-memory SQLite, mocked LLM, FastAPI test client."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Make sure tests are deterministic and offline. We use direct assignment
# (not setdefault) so that a stray LLM_PROVIDER in the developer's shell
# cannot accidentally send real requests (and real money) from CI or local
# runs. The autouse fixture below clears the lru_cache so the new values
# are picked up.
os.environ["LLM_PROVIDER"] = "mock"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["APP_DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["INSIGHTLOOP_API_KEY"] = "test-write-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["SESSION_SECRET"] = "test-session-secret"

from app.ai import factory as llm_factory  # noqa: E402
from app.ai.mock_client import MockClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from main import create_app  # noqa: E402  (project-root entry point)


@pytest.fixture()
def test_db() -> Generator[Session, None, None]:
    """Yield a session backed by an in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """FastAPI test client with a per-test DB override."""
    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    # The `with TestClient(app) as c:` context manager already drives the
    # FastAPI lifespan startup, so we don't need a manual `c.get("/")` here.
    with TestClient(app) as c:
        c.headers.update({"Authorization": "Bearer test-write-key"})
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_llm() -> MockClient:
    return MockClient()


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    llm_factory.get_llm_client.cache_clear()
    yield
    get_settings.cache_clear()
    llm_factory.get_llm_client.cache_clear()
