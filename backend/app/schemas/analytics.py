"""Currency-safe travel analytics schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ResponseModel


class CurrencyAnalytics(ResponseModel):
    currency: str
    itinerary_count: int
    planned_budget: float
    estimated_cost: float
    activity_estimate: float
    line_items: dict[str, float] = Field(default_factory=dict)


class TopDestination(ResponseModel):
    destination_name: str
    destination_place_id: str | None = None
    trip_count: int


class MonthlyTrips(ResponseModel):
    month: str
    trip_count: int


class TravelAnalyticsResponse(ResponseModel):
    total_itineraries: int
    upcoming_trips: int
    active_trips: int
    completed_trips: int
    draft_trips: int
    archived_trips: int
    reviews_count: int
    currencies: list[CurrencyAnalytics] = Field(default_factory=list)
    top_destinations: list[TopDestination] = Field(default_factory=list)
    monthly_itineraries: list[MonthlyTrips] = Field(default_factory=list)
    activity_counts: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
