"""Abstract base class for LLM providers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

SYSTEM_PROMPT = """You are InsightLoop, an expert customer-feedback analyst.
You always respond with a single JSON object that matches this exact schema:
{
  "sentiment": "positive" | "neutral" | "negative",
  "score": number between 0 and 100,    // 0 = extremely negative, 100 = extremely positive
  "topics": array of 1-5 short lowercase topic tags, e.g. ["pricing", "ui", "support"],
  "urgency": integer 1-5,                // 5 = requires immediate attention
  "summary": one concise sentence (<= 200 chars),
  "suggested_actions": array of 1-3 short, concrete, actionable next steps
}
Never add prose, markdown, or code fences around the JSON."""


class LLMError(RuntimeError):
    """Raised when an LLM call fails or returns invalid output."""


@dataclass
class LLMResponse:
    """Normalized result from any LLM provider."""

    sentiment: str
    score: float
    topics: list[str]
    urgency: int
    summary: str
    suggested_actions: list[str]
    raw: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentiment": self.sentiment,
            "score": self.score,
            "topics": self.topics,
            "urgency": self.urgency,
            "summary": self.summary,
            "suggested_actions": self.suggested_actions,
        }


class LLMClient(ABC):
    """Common interface for every supported LLM provider."""

    provider_name: str = "base"
    model_name: str = ""

    @abstractmethod
    def analyze_feedback(self, text: str) -> LLMResponse: ...

    @staticmethod
    def _build_user_prompt(text: str) -> str:
        return (
            "Analyze the following customer feedback and respond with the JSON object "
            "described in the system message.\n\n"
            f'FEEDBACK:\n"""\n{text.strip()}\n"""'
        )

    @staticmethod
    def parse_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
        """Tolerantly extract the JSON object from an LLM response."""
        if isinstance(payload, dict):
            data = payload
        else:
            text = payload.strip()
            # Strip common code-fence wrappers just in case.
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
                text = text.strip()
            # Find the outermost JSON object.
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise LLMError(f"No JSON object found in response: {payload[:200]!r}")
            text = text[start : end + 1]
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LLMError(f"Invalid JSON from LLM: {exc}") from exc

        # Normalize / validate fields.
        sentiment = str(data.get("sentiment", "neutral")).lower().strip()
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"

        try:
            score = float(data.get("score", 50.0))
        except (TypeError, ValueError):
            score = 50.0
        score = max(0.0, min(100.0, score))

        try:
            urgency = int(data.get("urgency", 1))
        except (TypeError, ValueError):
            urgency = 1
        urgency = max(1, min(5, urgency))

        topics = data.get("topics") or []
        if not isinstance(topics, list):
            topics = []
        seen: set[str] = set()
        deduped: list[str] = []
        for t in topics:
            norm = str(t).strip().lower()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(norm)
        topics = deduped[:5]

        actions = data.get("suggested_actions") or []
        if not isinstance(actions, list):
            actions = []
        actions = [str(a).strip() for a in actions if str(a).strip()][:3]

        summary = str(data.get("summary", "")).strip()[:500]

        return {
            "sentiment": sentiment,
            "score": score,
            "topics": topics,
            "urgency": urgency,
            "summary": summary,
            "suggested_actions": actions,
        }
