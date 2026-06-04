"""InsightLoop — entry point.

Run with:
    python main.py
or
    uvicorn main:app --reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routes import api_feedback, api_insights, api_reports, pages


def _configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_data_dir()
    init_db()
    logging.getLogger("insightloop").info(
        "Started InsightLoop with provider=%s, host=%s:%s",
        settings.llm_provider,
        settings.app_host,
        settings.app_port,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="InsightLoop",
        version="0.1.0",
        description="AI-powered customer feedback analyzer for small businesses.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    static_dir: Path = settings.static_dir
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(pages.router)
    app.include_router(api_feedback.router)
    app.include_router(api_insights.router)
    app.include_router(api_reports.router)

    return app


app = create_app()


if __name__ == "__main__":
    _configure_logging()
    s = get_settings()
    uvicorn.run(
        "main:app",
        host=s.app_host,
        port=s.app_port,
        reload=s.app_debug,
        log_level="info",
    )
