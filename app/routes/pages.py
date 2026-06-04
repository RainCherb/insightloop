"""HTML page routes (Jinja2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.ai.factory import get_llm_client
from app.config import get_settings
from app.database import get_db
from app.services import insights_service
from app.templating import templates

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"settings": get_settings()},
    )


@router.get("/analyze", response_class=HTMLResponse)
def analyze_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "analyze.html",
        {"settings": get_settings()},
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "settings": get_settings(),
            "summary": insights_service.summary(db),
        },
    )


@router.get("/feedback", response_class=HTMLResponse)
def feedback_list_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    from app.services.feedback_service import FeedbackFilter, list_feedback

    rows = list_feedback(db, FeedbackFilter(limit=200))
    return templates.TemplateResponse(
        request,
        "feedback_list.html",
        {
            "settings": get_settings(),
            "rows": rows,
        },
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "reports.html",
        {"settings": get_settings()},
    )


@router.get("/health", include_in_schema=False)
def health() -> dict:
    try:
        client = get_llm_client()
        return {"status": "ok", "provider": client.provider_name}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "error": str(exc)}
