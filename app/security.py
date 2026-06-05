"""Authentication and CSRF helpers for mutating API routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Header, HTTPException, Request, status
from fastapi.responses import Response

from app.config import Settings, get_settings

SESSION_COOKIE_NAME = "insightloop_session"
CSRF_COOKIE_NAME = "insightloop_csrf"
SESSION_TTL_SECONDS = 12 * 60 * 60


def write_auth_configured(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    return bool(cfg.insightloop_api_key or cfg.admin_password)


def _secret(settings: Settings) -> str:
    return settings.session_secret or settings.admin_password or settings.insightloop_api_key


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign_payload(payload: dict[str, Any], settings: Settings) -> str:
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_secret(settings).encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return f"{body}.{_b64encode(sig.digest())}"


def _load_payload(token: str, settings: Settings) -> dict[str, Any] | None:
    if not token or "." not in token or not _secret(settings):
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(
        _secret(settings).encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual = _b64decode(signature)
        if not hmac.compare_digest(actual, expected):
            return None
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload if isinstance(payload, dict) else None


def current_admin(request: Request, settings: Settings | None = None) -> str | None:
    cfg = settings or get_settings()
    payload = _load_payload(request.cookies.get(SESSION_COOKIE_NAME, ""), cfg)
    if payload is None:
        return None
    user = str(payload.get("sub") or "")
    return user if user else None


def set_login_cookies(response: Response, settings: Settings) -> None:
    csrf = secrets.token_urlsafe(32)
    payload = {
        "sub": settings.admin_username,
        "csrf": csrf,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    response.set_cookie(
        SESSION_COOKIE_NAME,
        _sign_payload(payload, settings),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf,
        max_age=SESSION_TTL_SECONDS,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
    )


def clear_login_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE_NAME)


def verify_admin_credentials(username: str, password: str, settings: Settings) -> bool:
    return (
        bool(settings.admin_password)
        and hmac.compare_digest(username, settings.admin_username)
        and hmac.compare_digest(password, settings.admin_password)
    )


def _valid_api_key(
    settings: Settings,
    authorization: str | None,
    insightloop_api_key: str | None,
) -> bool:
    if not settings.insightloop_api_key:
        return False
    candidates: list[str] = []
    if insightloop_api_key:
        candidates.append(insightloop_api_key)
    if authorization and authorization.lower().startswith("bearer "):
        candidates.append(authorization[7:].strip())
    return any(
        hmac.compare_digest(candidate, settings.insightloop_api_key) for candidate in candidates
    )


def require_write_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    insightloop_api_key: str | None = Header(default=None, alias="X-InsightLoop-API-Key"),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    settings = get_settings()
    if not write_auth_configured(settings):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Write protection is not configured. Set INSIGHTLOOP_API_KEY for API clients "
            "or ADMIN_PASSWORD for browser login.",
        )

    if _valid_api_key(settings, authorization, insightloop_api_key):
        return

    payload = _load_payload(request.cookies.get(SESSION_COOKIE_NAME, ""), settings)
    if payload is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_csrf = str(payload.get("csrf") or "")
    cookie_csrf = request.cookies.get(CSRF_COOKIE_NAME, "")
    if not (
        expected_csrf
        and csrf_token
        and hmac.compare_digest(cookie_csrf, expected_csrf)
        and hmac.compare_digest(csrf_token, expected_csrf)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid CSRF token")
