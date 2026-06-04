"""Aggregate insight endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import feedback_service, insights_service

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    return insights_service.summary(db)


@router.get("/trends")
def trends(days: int = Query(default=14, ge=1, le=90), db: Session = Depends(get_db)) -> list[dict]:
    return insights_service.trends(db, days=days)


@router.get("/topics")
def topics(
    limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)
) -> list[dict]:
    return insights_service.top_topics(db, limit=limit)


@router.get("/urgent")
def urgent(
    limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)
) -> list[dict]:
    rows = insights_service.urgent_items(db, limit=limit)
    return [feedback_service.feedback_to_dict(r) for r in rows]
