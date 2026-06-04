"""High-level analysis pipeline: text → LLM → persisted `Analysis` row."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.base import LLMClient, LLMError
from app.ai.factory import get_llm_client
from app.models import Analysis, Feedback
from app.schemas import FeedbackCreate

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    feedback: Feedback
    analysis: Analysis
    elapsed_ms: int


def analyze_and_persist(
    payload: FeedbackCreate,
    db: Session,
    llm: LLMClient | None = None,
) -> AnalysisResult:
    """Create a `Feedback` row, call the LLM, store the `Analysis` row.

    The whole operation is committed in a single transaction.
    """
    llm = llm or get_llm_client()
    feedback = Feedback(
        text=payload.text,
        source=payload.source or "manual",
        customer_email=str(payload.customer_email) if payload.customer_email else None,
    )
    db.add(feedback)
    db.flush()  # assign feedback.id

    started = time.perf_counter()
    try:
        llm_response = llm.analyze_feedback(payload.text)
    except LLMError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Unexpected LLM failure")
        raise

    analysis = Analysis(
        feedback_id=feedback.id,
        sentiment=llm_response.sentiment,
        score=float(llm_response.score),
        topics=list(llm_response.topics),
        urgency=int(llm_response.urgency),
        summary=llm_response.summary,
        suggested_actions=list(llm_response.suggested_actions),
        raw_response=llm_response.raw or {},
        provider=llm_response.provider or llm.provider_name,
        model=llm_response.model or "",
    )
    db.add(analysis)
    db.commit()
    db.refresh(feedback)
    db.refresh(analysis)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "analyzed feedback id=%s sentiment=%s score=%.1f urgency=%s provider=%s in %dms",
        feedback.id,
        analysis.sentiment,
        analysis.score,
        analysis.urgency,
        analysis.provider,
        elapsed_ms,
    )
    return AnalysisResult(feedback=feedback, analysis=analysis, elapsed_ms=elapsed_ms)
