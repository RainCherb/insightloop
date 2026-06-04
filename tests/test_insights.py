"""Tests for the insights aggregations."""

from __future__ import annotations

from app.schemas import FeedbackCreate
from app.services import feedback_service, insights_service


def _ingest(db, texts):
    for t in texts:
        feedback_service.bulk_ingest([FeedbackCreate(text=t, source="test")], db)


def test_summary_empty(test_db):
    s = insights_service.summary(test_db)
    assert s["total"] == 0
    assert s["top_topics"] == []


def test_summary_counts(test_db):
    _ingest(
        test_db,
        [
            "Love the dashboard!",
            "Crash on launch, terrible.",
            "Pricing is fine.",
        ],
    )
    s = insights_service.summary(test_db)
    assert s["total"] == 3
    assert s["positive"] + s["neutral"] + s["negative"] == 3
    assert s["average_score"] > 0
    assert s["average_urgency"] > 0


def test_top_topics_sorted(test_db):
    _ingest(test_db, ["UI is intuitive.", "Great UI, clean.", "Pricing is high."])
    topics = insights_service.top_topics(test_db)
    assert topics
    counts = [t["count"] for t in topics]
    assert counts == sorted(counts, reverse=True)
    labels = {t["topic"] for t in topics}
    assert "ui" in labels
    assert "pricing" in labels


def test_urgent_items(test_db):
    _ingest(
        test_db,
        [
            "I want a refund immediately.",
            "Just love the new feature.",
            "Cancel my subscription, this is fraud.",
        ],
    )
    urgent = insights_service.urgent_items(test_db)
    assert urgent
    for fb in urgent:
        assert fb.analysis is not None
        assert fb.analysis.urgency >= 4


def test_trends_returns_buckets(test_db):
    _ingest(test_db, ["Great product."])
    trends = insights_service.trends(test_db, days=7)
    assert len(trends) == 7
    for row in trends:
        assert {"date", "positive", "neutral", "negative"} <= row.keys()
