"""Itinerary share-link schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import ResponseModel, StrictModel
from app.schemas.itineraries import BudgetEstimate, ItineraryDayResponse


class ShareCreateRequest(StrictModel):
    expires_in_days: int = Field(default=7, ge=1, le=365)


class ShareResponse(ResponseModel):
    id: UUID
    itinerary_id: UUID
    token: str
    share_url: str
    api_path: str
    expires_at: datetime
    created_at: datetime
    warning: str = (
        "Anyone with this link can view the shared itinerary until it expires or "
        "is revoked. Do not post it publicly if it contains sensitive details."
    )


class ShareSummary(ResponseModel):
    id: UUID
    itinerary_id: UUID
    expires_at: datetime | None = None
    is_expired: bool = False
    created_at: datetime


class ShareListResponse(ResponseModel):
    items: list[ShareSummary]
    total: int


class SharedItineraryResponse(ResponseModel):
    """Read-only public projection with owner-only fields removed."""

    id: UUID
    title: str
    summary: str | None = None
    destination_name: str
    destination_place_id: str | None = None
    destination_address: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    start_date: date
    end_date: date
    travellers: int
    currency: str
    status: str
    accommodation_preference: str
    transportation_preference: str
    pace: str
    interests: list[str] = Field(default_factory=list)
    budget_estimate: BudgetEstimate | None = None
    warnings: list[str] = Field(default_factory=list)
    days: list[ItineraryDayResponse] = Field(default_factory=list)
    recommendations: dict | None = None
    weather_summary: dict | None = None
    source_note: str = (
        "Shared read-only itinerary. Places and ratings come from Google Places; "
        "prices and budgets are estimates, not verified live prices."
    )
