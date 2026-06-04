"""Pydantic DTOs used by the API layer."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Sentiment = Literal["positive", "neutral", "negative"]


class FeedbackCreate(BaseModel):
    """Payload for creating a single feedback item."""

    text: str = Field(..., min_length=1, max_length=20_000)
    source: str = Field(default="manual", max_length=64)
    customer_email: EmailStr | None = None


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sentiment: Sentiment
    score: float = Field(..., ge=0.0, le=100.0)
    topics: list[str] = Field(default_factory=list)
    urgency: int = Field(..., ge=1, le=5)
    summary: str
    suggested_actions: list[str] = Field(default_factory=list)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    source: str
    customer_email: str | None = None
    created_at: datetime
    analysis: AnalysisOut | None = None


class BulkUploadResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class SummaryInsights(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    average_score: float
    average_urgency: float
    urgent_count: int
    top_topics: list[dict[str, int | str]]


class TrendPoint(BaseModel):
    date: str
    positive: int
    neutral: int
    negative: int


class TopicCount(BaseModel):
    topic: str
    count: int


class ProviderInfo(BaseModel):
    provider: str
    model: str
