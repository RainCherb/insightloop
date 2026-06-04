"""Export feedback + analyses to CSV, JSON, and PDF."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Analysis, Feedback
from app.services import insights_service

CSV_HEADERS = [
    "id",
    "created_at",
    "source",
    "customer_email",
    "text",
    "sentiment",
    "score",
    "topics",
    "urgency",
    "summary",
    "suggested_actions",
]


def _joined(db: Session):
    stmt = (
        select(Feedback)
        .options(selectinload(Feedback.analysis))
        .order_by(Feedback.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def to_csv(db: Session) -> str:
    rows = _joined(db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    for fb in rows:
        a: Analysis | None = fb.analysis
        writer.writerow(
            [
                fb.id,
                fb.created_at.isoformat() if fb.created_at else "",
                fb.source,
                fb.customer_email or "",
                fb.text,
                a.sentiment if a else "",
                a.score if a else "",
                ";".join(a.topics) if a and a.topics else "",
                a.urgency if a else "",
                a.summary if a else "",
                "; ".join(a.suggested_actions) if a and a.suggested_actions else "",
            ]
        )
    return buf.getvalue()


def to_json(db: Session) -> str:
    rows = _joined(db)
    payload = [
        {
            "id": fb.id,
            "text": fb.text,
            "source": fb.source,
            "customer_email": fb.customer_email,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
            "analysis": fb.analysis.to_dict() if fb.analysis else None,
        }
        for fb in rows
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_pdf(db: Session) -> bytes:
    """Render a one-page PDF summary of the current state."""
    summary = insights_service.summary(db)
    urgent = insights_service.urgent_items(db, limit=5)
    top_topics = summary["top_topics"][:6]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="InsightLoop report",
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    story: list = []

    story.append(Paragraph("<b>InsightLoop — Feedback Report</b>", styles["Title"]))
    story.append(
        Paragraph(
            f"Generated at {datetime.now(UTC).isoformat(timespec='seconds')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 12))

    kpi_data = [
        ["Total", "Positive", "Neutral", "Negative", "Avg score", "Urgent"],
        [
            str(summary["total"]),
            str(summary["positive"]),
            str(summary["neutral"]),
            str(summary["negative"]),
            f"{summary['average_score']:.1f}",
            str(summary["urgent_count"]),
        ],
    ]
    kpi_table = Table(kpi_data, hAlign="LEFT")
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("<b>Top topics</b>", styles["Heading3"]))
    if top_topics:
        topic_rows = [["Topic", "Count"]] + [[t["topic"], str(t["count"])] for t in top_topics]
        topic_table = Table(topic_rows, hAlign="LEFT", colWidths=[240, 80])
        topic_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        story.append(topic_table)
    else:
        story.append(Paragraph("<i>No data yet.</i>", styles["Normal"]))
    story.append(Spacer(1, 18))

    story.append(Paragraph("<b>Most urgent items</b>", styles["Heading3"]))
    if urgent:
        urgent_rows = [["#", "Text", "Sentiment", "Urgency"]]
        for fb in urgent:
            a = fb.analysis
            text_preview = (fb.text or "")[:80] + ("…" if fb.text and len(fb.text) > 80 else "")
            urgent_rows.append(
                [
                    str(fb.id),
                    text_preview,
                    a.sentiment if a else "-",
                    str(a.urgency) if a else "-",
                ]
            )
        urgent_table = Table(urgent_rows, hAlign="LEFT", colWidths=[30, 320, 70, 60])
        urgent_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7f1d1d")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(urgent_table)
    else:
        story.append(Paragraph("<i>No urgent items.</i>", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
