"""SQLAlchemy ORM models for feedback and its analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Feedback(Base):
    """A single piece of raw customer feedback."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    analysis: Mapped[Analysis | None] = relationship(
        "Analysis",
        back_populates="feedback",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Analysis(Base):
    """The structured AI analysis of a single feedback item."""

    __tablename__ = "analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("feedback.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    sentiment: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    urgency: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    suggested_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    feedback: Mapped[Feedback] = relationship("Feedback", back_populates="analysis")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "feedback_id": self.feedback_id,
            "sentiment": self.sentiment,
            "score": self.score,
            "topics": self.topics,
            "urgency": self.urgency,
            "summary": self.summary,
            "suggested_actions": self.suggested_actions,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
