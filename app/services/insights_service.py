"""Aggregate analytics on top of stored analyses."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Analysis, Feedback


def _iter_analyses(db: Session) -> Iterable[Analysis]:
    """Stream analyses row-by-row. Callers that need a list should wrap
    the result in `list(...)` themselves.
    """
    stmt = select(Analysis)
    yield from db.scalars(stmt)


def summary(db: Session) -> dict:
    analyses = list(_iter_analyses(db))
    total = len(analyses)
    if total == 0:
        return {
            "total": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "average_score": 0.0,
            "average_urgency": 0.0,
            "urgent_count": 0,
            "top_topics": [],
        }

    sentiment_counts = Counter(a.sentiment for a in analyses)
    avg_score = sum(a.score for a in analyses) / total
    avg_urgency = sum(a.urgency for a in analyses) / total
    urgent = sum(1 for a in analyses if a.urgency >= 4)
    topic_counter: Counter[str] = Counter()
    for a in analyses:
        for t in a.topics or []:
            topic_counter[t] += 1
    top_topics = [{"topic": t, "count": c} for t, c in topic_counter.most_common(10)]
    return {
        "total": total,
        "positive": sentiment_counts.get("positive", 0),
        "neutral": sentiment_counts.get("neutral", 0),
        "negative": sentiment_counts.get("negative", 0),
        "average_score": round(avg_score, 2),
        "average_urgency": round(avg_urgency, 2),
        "urgent_count": urgent,
        "top_topics": top_topics,
    }


def trends(db: Session, days: int = 14) -> list[dict]:
    """Per-day sentiment counts for the last `days` days."""
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    for d in (start + timedelta(days=i) for i in range(days)):
        buckets[d.isoformat()]

    stmt = select(Feedback, Analysis).join(Analysis, Analysis.feedback_id == Feedback.id)
    for fb, a in db.execute(stmt).all():
        if fb.created_at is None:
            continue
        d = fb.created_at.astimezone(UTC).date()
        if d < start or d > today:
            continue
        bucket = buckets[d.isoformat()]
        bucket[a.sentiment] = bucket.get(a.sentiment, 0) + 1

    out: list[dict] = []
    for d in sorted(buckets):
        out.append({"date": d, **buckets[d]})
    return out


def top_topics(db: Session, limit: int = 10) -> list[dict]:
    counter: Counter[str] = Counter()
    for a in _iter_analyses(db):
        for t in a.topics or []:
            counter[t] += 1
    return [{"topic": t, "count": c} for t, c in counter.most_common(limit)]


def urgent_items(db: Session, limit: int = 20) -> list[Feedback]:
    stmt = (
        select(Feedback)
        .join(Analysis, Analysis.feedback_id == Feedback.id)
        .where(Analysis.urgency >= 4)
        .options(selectinload(Feedback.analysis))
        .order_by(Feedback.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
