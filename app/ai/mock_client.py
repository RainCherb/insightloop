"""Deterministic, dependency-free mock LLM client.

It does not call any external service. Given the same input text, it always
returns the same analysis — which makes it ideal for demos, CI, and offline
development. The analysis is derived from a small heuristic + a hash of the
text, so it looks plausible but is **not** intelligent.
"""

from __future__ import annotations

import hashlib
import re

from app.ai.base import LLMClient, LLMResponse

POSITIVE_WORDS = {
    "love",
    "great",
    "awesome",
    "excellent",
    "amazing",
    "perfect",
    "fantastic",
    "wonderful",
    "happy",
    "best",
    "easy",
    "fast",
    "smooth",
    "helpful",
    "good",
    "nice",
    "impressive",
    "recommend",
    "delighted",
    "satisfied",
    "pleased",
    "outstanding",
    "intuitive",
    "reliable",
    "saved",
    "win",
}
NEGATIVE_WORDS = {
    "hate",
    "bad",
    "terrible",
    "awful",
    "worst",
    "broken",
    "bug",
    "crash",
    "crashes",
    "slow",
    "expensive",
    "frustrating",
    "angry",
    "disappointed",
    "useless",
    "horrible",
    "annoying",
    "painful",
    "confusing",
    "failed",
    "fail",
    "issue",
    "issues",
    "problem",
    "problems",
    "error",
    "errors",
    "missing",
    "unhappy",
    "cancel",
    "refund",
}
URGENT_TRIGGERS = {
    "refund",
    "cancel",
    "lawsuit",
    "legal",
    "down",
    "outage",
    "lost",
    "stolen",
    "chargeback",
    "complaint",
    "fraud",
    "scam",
    "asap",
    "urgent",
    "immediately",
    "data loss",
    "leak",
    "breach",
}

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pricing": ("price", "pricing", "expensive", "cost", "cheap", "subscription", "billing"),
    "ui": ("ui", "interface", "design", "layout", "dashboard", "look", "feel"),
    "ux": ("ux", "experience", "usability", "intuitive", "confusing", "navigation"),
    "performance": ("slow", "lag", "speed", "fast", "performance", "loading", "freeze"),
    "support": ("support", "helpdesk", "ticket", "agent", "response", "reply"),
    "documentation": ("docs", "documentation", "guide", "tutorial", "readme"),
    "onboarding": ("onboarding", "signup", "sign up", "register", "first time"),
    "mobile": ("mobile", "ios", "android", "phone", "app"),
    "integration": ("integration", "api", "webhook", "zapier", "sync"),
    "features": ("feature", "missing", "wish", "request", "would be nice"),
    "bug": ("bug", "broken", "crash", "error", "issue"),
    "security": ("security", "password", "2fa", "breach", "leak"),
    "billing": ("billing", "invoice", "charge", "refund", "payment"),
    "reliability": ("reliable", "downtime", "outage", "down", "stable"),
    "communication": ("email", "notification", "spam", "message", "alert"),
}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _score_from_tokens(text: str) -> float:
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = max(1, pos + neg)
    base = 50.0 + 50.0 * (pos - neg) / total
    # Tiny deterministic jitter based on length, so scores vary but remain stable.
    jitter = (len(tokens) % 7) - 3
    return max(0.0, min(100.0, round(base + jitter, 1)))


def _topics_from_text(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(topic)
    if not found:
        found.append("general")
    return found[:5]


def _urgency_from_text(text: str, sentiment: str) -> int:
    lowered = text.lower()
    if any(trigger in lowered for trigger in URGENT_TRIGGERS):
        return 5
    if sentiment == "negative" and _word_count(text) > 30:
        return 4
    if sentiment == "negative":
        return 3
    if sentiment == "neutral":
        return 2
    return 1


def _suggested_actions(sentiment: str, topics: list[str], urgency: int) -> list[str]:
    if urgency >= 4:
        return [
            "Reply within 24 hours with a personal apology",
            "Open a high-priority ticket and assign an owner",
            "Schedule a follow-up call to confirm resolution",
        ]
    if sentiment == "negative":
        return [
            "Send a polite acknowledgement and ask for more detail",
            "Tag the conversation for the product team to review",
        ]
    if sentiment == "neutral":
        return [
            "Thank the customer and surface the relevant docs",
        ]
    return [
        "Thank the customer and ask whether they would share a public review",
    ]


class MockClient(LLMClient):
    provider_name = "mock"

    def __init__(self, model: str = "mock-deterministic-v1") -> None:
        self._model = model

    def analyze_feedback(self, text: str) -> LLMResponse:
        if not text or not text.strip():
            raise ValueError("text must not be empty")

        score = _score_from_tokens(text)
        sentiment = "positive" if score >= 65 else "negative" if score <= 40 else "neutral"
        topics = _topics_from_text(text)
        urgency = _urgency_from_text(text, sentiment)
        suggested = _suggested_actions(sentiment, topics, urgency)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        summary = (
            f"[mock {digest}] {sentiment.capitalize()} feedback about "
            f"{', '.join(topics)} with urgency {urgency}/5."
        )

        raw = {
            "sentiment": sentiment,
            "score": score,
            "topics": topics,
            "urgency": urgency,
            "summary": summary,
            "suggested_actions": suggested,
            "_mock": True,
        }
        return LLMResponse(
            sentiment=sentiment,
            score=score,
            topics=topics,
            urgency=urgency,
            summary=summary,
            suggested_actions=suggested,
            raw=raw,
            provider=self.provider_name,
            model=self._model,
        )
