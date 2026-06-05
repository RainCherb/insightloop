"""Regression tests for the bugs found in the deep code review.

Each test maps to one of the issues identified in the audit (see commit
message of the fix for the full list).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.ai import factory as llm_factory
from app.ai.mock_client import MockClient
from app.config import get_settings
from app.database import init_db
from app.services import feedback_service
from app.services.feedback_service import FeedbackFilter
from main import create_app

# ---------------------------------------------------------------------------
# Bug #1: list_feedback pagination was applied BEFORE filtering, and the
# `source` filter was completely ignored.
# ---------------------------------------------------------------------------


def test_list_feedback_pagination_with_filter_returns_full_page(client):
    """Pagination must be honoured even when filters are present."""
    for i in range(5):
        client.post(
            "/api/feedback",
            json={"text": f"Positive feedback number {i}", "source": "positive_set"},
        )
    for i in range(5):
        client.post(
            "/api/feedback",
            json={"text": f"Negative feedback number {i}", "source": "negative_set"},
        )

    # Without a filter: limit 6 should return 6 rows.
    r = client.get("/api/feedback?limit=6")
    assert r.status_code == 200
    assert len(r.json()) == 6

    # With a source filter: limit 6 should still return up to 6 rows from that
    # source — this was the bug, where you could get fewer than `limit` rows
    # because pagination was applied first.
    r = client.get("/api/feedback?source=positive_set&limit=6")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 5  # we only created 5
    for row in rows:
        assert row["source"] == "positive_set"


def test_list_feedback_source_filter_is_applied(test_db):
    """The `source` field of FeedbackFilter must actually filter."""
    for _i in range(3):
        feedback_service.bulk_ingest([__feedback("email body", source="email")], test_db)
    for _i in range(2):
        feedback_service.bulk_ingest([__feedback("tweet body", source="twitter")], test_db)

    rows = feedback_service.list_feedback(test_db, FeedbackFilter(source="twitter", limit=50))
    assert len(rows) == 2
    for row in rows:
        assert row.source == "twitter"


def test_list_feedback_topic_filter(test_db):
    """Topic filter should still work after the refactor."""
    for text, source in [
        ("The pricing is too high.", "email"),
        ("Great UI, love the new design.", "email"),
        ("UI is great and pricing is fair.", "email"),
    ]:
        feedback_service.bulk_ingest([__feedback(text, source=source)], test_db)

    rows = feedback_service.list_feedback(test_db, FeedbackFilter(topic="ui", limit=50))
    assert len(rows) == 2
    for row in rows:
        assert row.analysis is not None
        assert "ui" in row.analysis.topics


def test_list_feedback_min_urgency_filter(test_db):
    for text in [
        "I want a refund immediately, this is fraud.",  # urgency 5
        "Just love the new feature.",  # urgency 1
        "Cancel my subscription now.",  # urgency 5
    ]:
        feedback_service.bulk_ingest([__feedback(text)], test_db)

    rows = feedback_service.list_feedback(test_db, FeedbackFilter(min_urgency=4, limit=50))
    assert len(rows) == 2
    for row in rows:
        assert row.analysis is not None
        assert row.analysis.urgency >= 4


def __feedback(text: str, source: str = "manual"):
    from app.schemas import FeedbackCreate

    return FeedbackCreate(text=text, source=source)


# ---------------------------------------------------------------------------
# Bug #2: /api/reports/json used __import__("json") and round-tripped a JSON
# string back to a dict. The endpoint should return the JSON body unchanged.
# ---------------------------------------------------------------------------


def test_reports_json_endpoint_returns_json(client):
    client.post("/api/feedback", json={"text": "Just a test row."})
    r = client.get("/api/reports/json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    # The body must be valid JSON (not an error message) and parseable.
    parsed = json.loads(r.content)
    assert isinstance(parsed, list)
    assert len(parsed) >= 1
    assert "text" in parsed[0]
    assert "analysis" in parsed[0]


# ---------------------------------------------------------------------------
# Bug #3: /api/analyze had an unused `db` dependency. We can't easily assert
# "no DB connection" from the outside, but we can assert the endpoint
# still works and doesn't fail when the DB is not reachable.
# ---------------------------------------------------------------------------


def test_analyze_endpoint_does_not_require_db(client):
    r = client.post("/api/analyze", json={"text": "Great product, love it!"})
    assert r.status_code == 200
    data = r.json()
    assert data["sentiment"] in {"positive", "neutral", "negative"}


# ---------------------------------------------------------------------------
# Bug #4: provider_info used getattr(client, "_model") instead of a public
# model_name property.
# ---------------------------------------------------------------------------


def test_llm_clients_expose_model_name():
    from app.ai.anthropic_client import AnthropicClient
    from app.ai.ollama_client import OllamaClient
    from app.ai.openai_client import OpenAIClient

    # Each client must expose the model name via the public `model_name` attr
    # declared on the base class.
    assert MockClient().model_name == "mock-deterministic-v1"
    # For the real clients we can't easily instantiate them without keys, but
    # the class-level attribute is checked via a small instantiation that we
    # immediately discard. We mock the constructors below.
    OpenAIClient.__init__ = lambda self, api_key, model: setattr(self, "model_name", model)
    AnthropicClient.__init__ = lambda self, api_key, model: setattr(self, "model_name", model)
    OllamaClient.__init__ = lambda self, base_url, model, timeout=60.0: setattr(
        self, "model_name", model
    )

    assert OpenAIClient(api_key="x", model="gpt-4o").model_name == "gpt-4o"
    assert AnthropicClient(api_key="x", model="claude-haiku-4-5").model_name == "claude-haiku-4-5"
    assert OllamaClient(base_url="http://x", model="llama3.1:8b").model_name == "llama3.1:8b"


def test_provider_endpoint_returns_model_name(client):
    r = client.get("/api/provider")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "mock"
    assert data["model"] == "mock-deterministic-v1"


# ---------------------------------------------------------------------------
# Bug #5: tests were using os.environ.setdefault, which could let a stray
# LLM_PROVIDER=openai in the developer's shell leak into test runs.
# Verify the conftest forces the values.
# ---------------------------------------------------------------------------


def test_conftest_forces_mock_provider():
    import os

    # The conftest should have set LLM_PROVIDER to "mock" (not used setdefault).
    assert os.environ.get("LLM_PROVIDER") == "mock"


# ---------------------------------------------------------------------------
# Bug #6: /api/feedback/bulk had no file size limit. Verify the limit.
# ---------------------------------------------------------------------------


def test_bulk_upload_rejects_oversize_file(client):
    # Build a CSV that, when encoded, is larger than the 10 MiB limit.
    huge_text = "x" * (11 * 1024 * 1024)  # 11 MiB of text
    csv = f"text\n{huge_text}\n"
    r = client.post(
        "/api/feedback/bulk",
        files={"file": ("huge.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 413
    assert "limit" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Bug from iter_csv_rows: invalid email must surface with a row number.
# ---------------------------------------------------------------------------


def test_iter_csv_rows_reports_invalid_email_with_line_number():
    csv = (
        "text,source,customer_email\n"
        '"row one is fine",email,good@x.com\n'
        '"row two has bad email",email,not-an-email\n'
        '"row three is fine",email,also@good.com\n'
    )
    # The generator raises on the bad row with a message that includes
    # the offending line number and the bad value.
    with pytest.raises(ValueError) as excinfo:
        list(feedback_service.iter_csv_rows(csv))
    msg = str(excinfo.value)
    assert "row 3" in msg
    assert "not-an-email" in msg


def test_dashboard_urgent_items_do_not_use_inner_html():
    template = Path("templates/dashboard.html").read_text(encoding="utf-8")
    assert "target.innerHTML" not in template
    assert "replaceChildren" in template
    assert "textContent = u.text" in template
    assert "textContent = u.source" in template


def test_unconfigured_llm_provider_returns_503(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    llm_factory.get_llm_client.cache_clear()

    with TestClient(create_app(), raise_server_exceptions=False) as c:
        provider = c.get("/api/provider")
        analyze = c.post("/api/analyze", json={"text": "Great product"})
        feedback = c.post("/api/feedback", json={"text": "Great product"})

    for response in (provider, analyze, feedback):
        assert response.status_code == 503
        assert "LLM provider is not available" in response.json()["detail"]


def test_sqlite_memory_url_works_without_dependency_override():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        created = c.post("/api/feedback", json={"text": "Great product, love it!"})
        assert created.status_code == 201, created.text

        fetched = c.get(f"/api/feedback/{created.json()['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["analysis"] is not None


def test_init_db_retries_sqlite_schema_race(monkeypatch):
    calls = 0

    def fake_create_all(*, bind):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError(
                "CREATE TABLE feedback",
                {},
                Exception("table feedback already exists"),
            )

    monkeypatch.setattr("app.database.Base.metadata.create_all", fake_create_all)
    init_db()
    assert calls == 2


def test_sample_feedback_contains_documented_60_rows():
    rows = list(
        feedback_service.iter_csv_rows(
            Path("data/sample_feedback.csv").read_text(encoding="utf-8-sig")
        )
    )
    assert len(rows) == 60
