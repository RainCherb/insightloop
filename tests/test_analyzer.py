"""Tests for the LLM adapters (base parser + mock client)."""

from __future__ import annotations

from types import SimpleNamespace

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


def _valid_payload() -> dict:
    return {
        "sentiment": "positive",
        "score": 88,
        "topics": ["ui", "performance"],
        "urgency": 1,
        "summary": "Customer likes the dashboard.",
        "suggested_actions": ["Thank the customer"],
    }


def test_openai_client_sends_json_mode_and_parses_response(monkeypatch):
    from app.ai.openai_client import OpenAIClient

    captured: dict = {}

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create_completion))

        def _create_completion(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"sentiment":"positive","score":88,'
                                '"topics":["ui","performance"],"urgency":1,'
                                '"summary":"Customer likes the dashboard.",'
                                '"suggested_actions":["Thank the customer"]}'
                            )
                        )
                    )
                ]
            )

    monkeypatch.setattr("app.ai.openai_client.OpenAI", FakeOpenAI)

    client = OpenAIClient(api_key="test-key", model="gpt-test")
    result = client.analyze_feedback("Great dashboard")

    assert captured["api_key"] == "test-key"
    assert captured["model"] == "gpt-test"
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"][0]["role"] == "system"
    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.topics == ["ui", "performance"]


def test_anthropic_client_uses_tool_choice_and_parses_tool_input(monkeypatch):
    from app.ai.anthropic_client import ANALYSIS_TOOL, AnthropicClient

    captured: dict = {}

    class FakeAnthropic:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.messages = SimpleNamespace(create=self._create_message)

        def _create_message(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name=ANALYSIS_TOOL["name"],
                        input=_valid_payload(),
                    )
                ]
            )

    monkeypatch.setattr("app.ai.anthropic_client.Anthropic", FakeAnthropic)

    client = AnthropicClient(api_key="test-key", model="claude-test")
    result = client.analyze_feedback("Great dashboard")

    assert captured["api_key"] == "test-key"
    assert captured["model"] == "claude-test"
    assert captured["tools"] == [ANALYSIS_TOOL]
    assert captured["tool_choice"] == {"type": "tool", "name": ANALYSIS_TOOL["name"]}
    assert result.provider == "anthropic"
    assert result.model == "claude-test"
    assert result.score == 88.0


def test_ollama_client_posts_json_format_and_parses_response(monkeypatch):
    from app.ai.ollama_client import OllamaClient

    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "message": {
                    "content": (
                        '{"sentiment":"positive","score":88,'
                        '"topics":["ui","performance"],"urgency":1,'
                        '"summary":"Customer likes the dashboard.",'
                        '"suggested_actions":["Thank the customer"]}'
                    )
                }
            }

    class FakeHttpxClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def post(self, url: str, json: dict) -> FakeResponse:
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("app.ai.ollama_client.httpx.Client", FakeHttpxClient)

    client = OllamaClient(base_url="http://ollama.local/", model="llama-test", timeout=12)
    result = client.analyze_feedback("Great dashboard")

    assert captured["timeout"] == 12
    assert captured["url"] == "http://ollama.local/api/chat"
    assert captured["payload"]["model"] == "llama-test"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["format"] == "json"
    assert result.provider == "ollama"
    assert result.model == "llama-test"
    assert result.urgency == 1
