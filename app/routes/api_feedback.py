"""JSON API for feedback ingestion and listing."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.analyzer import analyze_and_persist
from app.database import get_db
from app.schemas import (
    AnalysisOut,
    FeedbackCreate,
    FeedbackOut,
)
from app.services import feedback_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> FeedbackOut:
    result = analyze_and_persist(payload, db)
    return FeedbackOut.model_validate(result.feedback)


@router.post("/feedback/bulk")
async def bulk_upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "text/plain"}:
        # Browsers often send `text/plain` or `application/octet-stream`; we still try.
        logger.info("bulk upload content_type=%s", file.content_type)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(415, f"File is not UTF-8 text: {exc}") from exc
    try:
        rows = list(feedback_service.iter_csv_rows(text))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not rows:
        raise HTTPException(400, "CSV is empty or has no `text` rows")
    return feedback_service.bulk_ingest(rows, db)


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(
    sentiment: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    min_urgency: int | None = Query(default=None, ge=1, le=5),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FeedbackOut]:
    flt = feedback_service.FeedbackFilter(
        sentiment=sentiment,
        topic=topic,
        min_urgency=min_urgency,
        source=source,
        limit=limit,
        offset=offset,
    )
    rows = feedback_service.list_feedback(db, flt)
    return [FeedbackOut.model_validate(r) for r in rows]


@router.get("/feedback/{feedback_id}", response_model=FeedbackOut)
def get_feedback(feedback_id: int, db: Session = Depends(get_db)) -> FeedbackOut:
    fb = feedback_service.get_feedback(db, feedback_id)
    if fb is None:
        raise HTTPException(404, "Feedback not found")
    return FeedbackOut.model_validate(fb)


@router.delete("/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(feedback_id: int, db: Session = Depends(get_db)) -> None:
    if not feedback_service.delete_feedback(db, feedback_id):
        raise HTTPException(404, "Feedback not found")


@router.get("/provider")
def provider_info() -> dict:
    from app.ai.factory import get_llm_client
    from app.config import get_settings

    settings = get_settings()
    client = get_llm_client()
    return {
        "provider": client.provider_name,
        "configured_provider": settings.llm_provider,
        "model": getattr(client, "_model", ""),
    }


@router.post("/analyze", response_model=AnalysisOut)
def analyze_only(payload: FeedbackCreate, db: Session = Depends(get_db)) -> AnalysisOut:
    """Analyze text but do NOT persist. Useful for live previews."""
    from app.ai.factory import get_llm_client

    llm = get_llm_client()
    resp = llm.analyze_feedback(payload.text)
    return AnalysisOut(
        sentiment=resp.sentiment,
        score=resp.score,
        topics=resp.topics,
        urgency=resp.urgency,
        summary=resp.summary,
        suggested_actions=resp.suggested_actions,
    )
