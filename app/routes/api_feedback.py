"""JSON API for feedback ingestion and listing."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.base import LLMError
from app.analyzer import analyze_and_persist
from app.database import get_db
from app.schemas import (
    AnalysisOut,
    FeedbackCreate,
    FeedbackOut,
)
from app.security import require_write_auth
from app.services import feedback_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

# Reject oversize uploads to keep memory bounded. 10 MiB is plenty for a
# 100k-row feedback CSV and small enough to keep the server responsive.
MAX_BULK_UPLOAD_BYTES = 10 * 1024 * 1024
_BULK_CHUNK_SIZE = 64 * 1024


@router.post(
    "/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_auth)],
)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> FeedbackOut:
    try:
        result = analyze_and_persist(payload, db)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"LLM provider is not available: {exc}",
        ) from exc
    return FeedbackOut.model_validate(result.feedback)


@router.post("/feedback/bulk", dependencies=[Depends(require_write_auth)])
def bulk_upload(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """Upload a CSV file and analyze every row. Synchronous on purpose so the
    sync SQLAlchemy session behaves predictably.
    """
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "text/plain"}:
        # Browsers often send `text/plain` or `application/octet-stream`; we still try.
        logger.info("bulk upload content_type=%s", file.content_type)

    # Stream the upload in chunks so a malicious or accidental huge file
    # doesn't OOM the process.
    chunks: list[bytes] = []
    total = 0
    while chunk := file.file.read(_BULK_CHUNK_SIZE):
        total += len(chunk)
        if total > MAX_BULK_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"CSV exceeds the {MAX_BULK_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    raw = b"".join(chunks)

    # Try UTF-8 first (with BOM stripped) and fall back to latin-1 so a
    # spreadsheet exported on a Windows machine doesn't get rejected outright.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, f"File is not decodable as text: {exc}") from exc

    try:
        rows = list(feedback_service.iter_csv_rows(text))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not rows:
        raise HTTPException(400, "CSV is empty or has no `text` rows")

    try:
        from app.ai.factory import get_llm_client

        get_llm_client()
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"LLM provider is not available: {exc}",
        ) from exc

    return feedback_service.bulk_ingest(rows, db).model_dump()


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


@router.delete(
    "/feedback/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_write_auth)],
)
def delete_feedback(feedback_id: int, db: Session = Depends(get_db)) -> None:
    if not feedback_service.delete_feedback(db, feedback_id):
        raise HTTPException(404, "Feedback not found")


@router.get("/provider")
def provider_info() -> dict:
    from app.ai.factory import get_llm_client
    from app.config import get_settings

    settings = get_settings()
    try:
        client = get_llm_client()
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"LLM provider is not available: {exc}",
        ) from exc
    return {
        "provider": client.provider_name,
        "configured_provider": settings.llm_provider,
        "model": client.model_name,
    }


@router.post("/analyze", response_model=AnalysisOut, dependencies=[Depends(require_write_auth)])
def analyze_only(payload: FeedbackCreate) -> AnalysisOut:
    """Analyze text but do NOT persist. Useful for live previews."""
    from app.ai.factory import get_llm_client

    try:
        llm = get_llm_client()
        resp = llm.analyze_feedback(payload.text)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"LLM provider is not available: {exc}",
        ) from exc
    return AnalysisOut(
        sentiment=resp.sentiment,
        score=resp.score,
        topics=resp.topics,
        urgency=resp.urgency,
        summary=resp.summary,
        suggested_actions=resp.suggested_actions,
    )
