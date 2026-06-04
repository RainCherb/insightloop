"""Tests for the LLM adapters (base parser + mock client)."""

from __future__ import annotations

import pytest

from app.ai.base import LLMError
from app.ai.mock_client import MockClient


def test_mock_client_deterministic():
    client = MockClient()
    text = "The dashboard is great and fast."
    a = client.analyze_feedback(text)
    b = client.analyze_feedback(text)
    assert a == b
    assert a.provider == "mock"
    assert 0.0 <= a.score <= 100.0
    assert 1 <= a.urgency <= 5
    assert a.sentiment in {"positive", "neutral", "negative"}


def test_mock_client_empty_raises():
    client = MockClient()
    with pytest.raises(ValueError):
        client.analyze_feedback("   ")


def test_mock_client_negative_sentiment():
    client = MockClient()
    out = client.analyze_feedback("The app is broken, crashes constantly, terrible support.")
    assert out.sentiment == "negative"
    assert "bug" in out.topics or "support" in out.topics


def test_mock_client_urgent_triggers():
    client = MockClient()
    out = client.analyze_feedback("I want a refund immediately, this is fraud.")
    assert out.urgency == 5
    assert out.sentiment == "negative"


def test_parse_payload_strips_code_fence():
    from app.ai.base import LLMClient

    text = '```json\n{"sentiment":"positive","score":80,"topics":["ui"],"urgency":1,"summary":"Nice.","suggested_actions":["Reply"]}\n```'
    parsed = LLMClient.parse_payload(text)
    assert parsed["sentiment"] == "positive"
    assert parsed["score"] == 80.0


def test_parse_payload_clamps_invalid_values():
    from app.ai.base import LLMClient

    parsed = LLMClient.parse_payload(
        {
            "sentiment": "WHAT",
            "score": 9999,
            "topics": ["Pricing", "PRICING", ""],
            "urgency": 42,
            "summary": "x" * 1000,
            "suggested_actions": ["a", "b", "c", "d"],
        }
    )
    assert parsed["sentiment"] == "neutral"
    assert parsed["score"] == 100.0
    assert parsed["topics"] == ["pricing"]
    assert parsed["urgency"] == 5
    assert len(parsed["summary"]) <= 500
    assert len(parsed["suggested_actions"]) == 3


def test_parse_payload_handles_plain_text():
    from app.ai.base import LLMClient

    with pytest.raises(LLMError):
        LLMClient.parse_payload("no json here at all")
