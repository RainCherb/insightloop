"""Shared Jinja2 environment."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import get_settings

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))
