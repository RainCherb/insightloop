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
    """Return feedback matching the filter, paginated correctly.

    All filters except `topic` are pushed into SQL (so pagination is correct).
    `topic` is applied in Python because SQLite has no clean way to query inside
    a JSON array; we therefore over-fetch for that one filter and slice in
    Python. The number of topic tags per feedback is small (max 5), so the
    in-memory cost is bounded.
    """
    has_analysis_filter = bool(flt.sentiment) or flt.min_urgency is not None
    stmt = select(Feedback).options(selectinload(Feedback.analysis))

    if has_analysis_filter:
        # Inner join drops feedback that has no analysis row.
        stmt = stmt.join(Analysis, Analysis.feedback_id == Feedback.id)
        if flt.sentiment:
            stmt = stmt.where(Analysis.sentiment == flt.sentiment)
        if flt.min_urgency is not None:
            stmt = stmt.where(Analysis.urgency >= flt.min_urgency)

    if flt.source:
        stmt = stmt.where(Feedback.source == flt.source)

    stmt = stmt.order_by(Feedback.created_at.desc())

    if flt.topic:
        # Fetch the full matching window, then filter by topic in Python and
        # slice for pagination. Documented limitation.
        all_rows = list(db.scalars(stmt).all())
        filtered = [
            fb
            for fb in all_rows
            if fb.analysis is not None and flt.topic in (fb.analysis.topics or [])
        ]
        if flt.limit <= 0:
            return filtered[flt.offset :]
        return filtered[flt.offset : flt.offset + flt.limit]

    if flt.limit > 0:
        stmt = stmt.limit(flt.limit).offset(flt.offset)
    return list(db.scalars(stmt).unique().all())


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
    for line_no, raw in enumerate(reader, start=2):  # header is line 1
        text = (raw.get("text") or "").strip()
        if not text:
            continue
        email = (raw.get("customer_email") or "").strip() or None
        try:
            yield FeedbackCreate(
                text=text,
                source=(raw.get("source") or "csv").strip() or "csv",
                customer_email=email,
            )
        except Exception as exc:  # noqa: BLE001
            # Re-raise with the offending row number so the user can find it.
            raise ValueError(
                f"row {line_no}: invalid value for column `customer_email={email!r}` — {exc}"
            ) from exc


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
