"""Interest-ranked recommendation schemas backed by Google Places."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ResponseModel, StrictModel
from app.schemas.destinations import PlaceSummary


class RecommendationRequest(StrictModel):
    destination: str = Field(min_length=2, max_length=200)
    destination_place_id: str | None = Field(default=None, max_length=512)
    interests: list[str] = Field(default_factory=list, max_length=20)
    budget_level: Literal["economy", "moderate", "premium"] | None = None
    dietary_preferences: list[str] = Field(default_factory=list, max_length=20)
    include_hotels: bool = True
    radius_m: int = Field(default=10_000, ge=500, le=50_000)
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("interests", "dietary_preferences")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        return [value.strip()[:80] for value in values if value.strip()]


class RecommendationItem(PlaceSummary):
    score: float
    reason: str


class RecommendationResponse(ResponseModel):
    destination: str
    destination_place_id: str | None = None
    attractions: list[RecommendationItem] = Field(default_factory=list)
    restaurants: list[RecommendationItem] = Field(default_factory=list)
    hotels: list[RecommendationItem] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str = "Google Places API (New)"
    ranking_method: str = "Deterministic interest, rating, and review-count ranking"
    generated_at: datetime
