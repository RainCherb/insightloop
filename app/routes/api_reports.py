"""Report download endpoints (CSV / JSON / PDF)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/csv")
def download_csv(db: Session = Depends(get_db)) -> Response:
    body = report_service.to_csv(db)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="insightloop.csv"'},
    )


@router.get("/json")
def download_json(db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(
        content=__import__("json").loads(report_service.to_json(db)),
        headers={"Content-Disposition": 'attachment; filename="insightloop.json"'},
    )


@router.get("/pdf")
def download_pdf(db: Session = Depends(get_db)) -> Response:
    body = report_service.to_pdf(db)
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="insightloop-report.pdf"'},
    )
