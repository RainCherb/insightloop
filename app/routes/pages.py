"""HTML page routes (Jinja2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.ai.factory import get_llm_client
from app.config import get_settings
from app.database import get_db
from app.security import (
    clear_login_cookies,
    current_admin,
    set_login_cookies,
    verify_admin_credentials,
    write_auth_configured,
)
from app.services import insights_service
from app.templating import templates

router = APIRouter(include_in_schema=False)


def _template_context(request: Request, **extra) -> dict:
    settings = get_settings()
    return {
        "settings": settings,
        "auth": {
            "configured": write_auth_configured(settings),
            "user": current_admin(request, settings),
        },
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        _template_context(request),
    )


@router.get("/analyze", response_class=HTMLResponse)
def analyze_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "analyze.html",
        _template_context(request),
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _template_context(request, summary=insights_service.summary(db)),
    )


@router.get("/feedback", response_class=HTMLResponse)
def feedback_list_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    from app.services.feedback_service import FeedbackFilter, list_feedback

    rows = list_feedback(db, FeedbackFilter(limit=200))
    return templates.TemplateResponse(
        request,
        "feedback_list.html",
        _template_context(request, rows=rows),
    )


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "reports.html",
        _template_context(request),
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        _template_context(request, error=None),
    )


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    settings = get_settings()
    if not settings.admin_password:
        return templates.TemplateResponse(
            request,
            "login.html",
            _template_context(
                request,
                error="Browser login is not configured. Set ADMIN_PASSWORD in .env.",
            ),
            status_code=503,
        )
    if not verify_admin_credentials(username, password, settings):
        return templates.TemplateResponse(
            request,
            "login.html",
            _template_context(request, error="Invalid username or password."),
            status_code=401,
        )

    response = RedirectResponse("/analyze", status_code=303)
    set_login_cookies(response, settings)
    return response


@router.post("/logout")
def logout() -> Response:
    response = RedirectResponse("/", status_code=303)
    clear_login_cookies(response)
    return response


@router.get("/health", include_in_schema=False)
def health() -> dict:
    """Liveness probe: the process is up and the LLM client can be built.

    NB: this does *not* make a real call to the provider. Use a separate
    readiness probe if you need to verify the provider is reachable.
    """
    try:
        client = get_llm_client()
        return {"status": "ok", "provider": client.provider_name, "model": client.model_name}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "error": str(exc)}
