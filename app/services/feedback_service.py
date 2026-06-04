"""CRUD and bulk-ingest helpers for feedback + analysis."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analyzer import analyze_and_persist
from app.models import Analysis, Feedback
from app.schemas import BulkUploadResult, FeedbackCreate

logger = logging.getLogger(__name__)


@dataclass
class FeedbackFilter:
    sentiment: str | None = None
    topic: str | None = None
    min_urgency: int | None = None
    source: str | None = None
    limit: int = 100
    offset: int = 0


def list_feedback(db: Session, flt: FeedbackFilter) -> list[Feedback]:
    stmt = (
        select(Feedback)
        .options(selectinload(Feedback.analysis))
        .order_by(Feedback.created_at.desc())
    )
    if flt.limit > 0:
        stmt = stmt.limit(flt.limit).offset(flt.offset)
    rows = list(db.scalars(stmt).all())
    if flt.sentiment or flt.topic or flt.min_urgency:
        out: list[Feedback] = []
        for fb in rows:
            a = fb.analysis
            if a is None:
                continue
            if flt.sentiment and a.sentiment != flt.sentiment:
                continue
            if flt.topic and flt.topic not in (a.topics or []):
                continue
            if flt.min_urgency is not None and a.urgency < flt.min_urgency:
                continue
            out.append(fb)
        return out
    return rows


def get_feedback(db: Session, feedback_id: int) -> Feedback | None:
    return db.scalars(
        select(Feedback).options(selectinload(Feedback.analysis)).where(Feedback.id == feedback_id)
    ).first()


def delete_feedback(db: Session, feedback_id: int) -> bool:
    fb = db.get(Feedback, feedback_id)
    if fb is None:
        return False
    db.delete(fb)
    db.commit()
    return True


def iter_csv_rows(csv_text: str) -> Iterable[FeedbackCreate]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None or "text" not in reader.fieldnames:
        raise ValueError("CSV must contain a `text` column")
    for raw in reader:
        text = (raw.get("text") or "").strip()
        if not text:
            continue
        yield FeedbackCreate(
            text=text,
            source=(raw.get("source") or "csv").strip() or "csv",
            customer_email=(raw.get("customer_email") or None),
        )


def bulk_ingest(rows: Iterable[FeedbackCreate], db: Session) -> BulkUploadResult:
    total = 0
    succeeded = 0
    failed = 0
    errors: list[str] = []
    for row in rows:
        total += 1
        try:
            analyze_and_persist(row, db)
            succeeded += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"row {total}: {exc}")
            logger.warning("bulk row %d failed: %s", total, exc)
    return BulkUploadResult(total=total, succeeded=succeeded, failed=failed, errors=errors)


def feedback_to_dict(fb: Feedback) -> dict:
    a: Analysis | None = fb.analysis
    return {
        "id": fb.id,
        "text": fb.text,
        "source": fb.source,
        "customer_email": fb.customer_email,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "analysis": a.to_dict() if a else None,
    }
