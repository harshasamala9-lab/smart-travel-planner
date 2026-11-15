"""Itinerary generation, storage, editing, and budget schemas."""

from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.enums import (
    AccommodationPreference,
    ActivityCategory,
    CostType,
    ItineraryStatus,
    TravelPace,
    TransportationPreference,
)
from app.schemas.common import ResponseModel, StrictModel

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


class BudgetLineItems(ResponseModel):
    transportation: float
    accommodation: float
    food: float
    activities: float
    other: float


class BudgetEstimate(ResponseModel):
    currency: str
    line_items: BudgetLineItems
    total: float
    per_person: float
    total_budget: float
    remaining: float
    over_budget: bool
    within_budget: bool
    utilization_percent: float
    warning: str | None = None
    accommodation_nights: int
    rooms: int
    cost_type: CostType = CostType.ESTIMATED
    assumptions: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "All amounts are planning estimates calculated from configurable average "
        "rates and AI-estimated activity costs. They are not verified live prices."
    )


class GenerateItineraryRequest(StrictModel):
    destination: str = Field(min_length=2, max_length=200)
    destination_place_id: str | None = Field(default=None, max_length=512)
    start_date: date
    end_date: date
    travellers: int = Field(default=1, ge=1, le=20)
    total_budget: float = Field(gt=0, le=1_000_000_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    activities: list[str] = Field(default_factory=list, max_length=20)
    interests: list[str] = Field(default_factory=list, max_length=20)
    accommodation_preference: AccommodationPreference = AccommodationPreference.MIDRANGE_HOTEL
    transportation_preference: TransportationPreference = TransportationPreference.MIXED
    pace: TravelPace = TravelPace.BALANCED
    origin: str | None = Field(default=None, max_length=160)
    dietary_preferences: list[str] = Field(default_factory=list, max_length=20)
    accessibility_needs: str | None = Field(default=None, max_length=500)
    additional_notes: str | None = Field(default=None, max_length=1000)
    include_routes: bool = True

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, value: str) -> str:
        value = value.upper()
        if not CURRENCY_PATTERN.fullmatch(value):
            raise ValueError("currency must be a 3-letter ISO 4217 code")
        return value

    @field_validator("interests", "activities", "dietary_preferences")
    @classmethod
    def _clean_list(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in values:
            value = item.strip()
            if value and value not in cleaned:
                cleaned.append(value[:80])
        return cleaned

    @model_validator(mode="after")
    def _validate_dates(self) -> "GenerateItineraryRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        duration = (self.end_date - self.start_date).days + 1
        if duration > 60:
            raise ValueError("Trips longer than 60 days are not supported")
        if self.start_date < date.today():
            raise ValueError("start_date cannot be in the past")
        return self


class ItineraryActivityResponse(ResponseModel):
    id: UUID
    place_id: str | None = None
    name: str
    category: ActivityCategory
    description: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    price_level: str | None = None
    opening_hours: list[str] = Field(default_factory=list)
    website_uri: str | None = None
    google_maps_uri: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    estimated_cost: float
    cost_type: CostType
    route_to_next: dict | None = None
    notes: str | None = None
    sort_order: int


class ItineraryDayResponse(ResponseModel):
    id: UUID
    day_number: int
    date: date
    title: str
    summary: str | None = None
    estimated_day_cost: float
    activities: list[ItineraryActivityResponse] = Field(default_factory=list)


class ItinerarySummaryResponse(ResponseModel):
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
    total_budget: float
    currency: str
    status: ItineraryStatus
    accommodation_preference: AccommodationPreference
    transportation_preference: TransportationPreference
    pace: TravelPace
    interests: list[str] = Field(default_factory=list)
    budget_estimate: BudgetEstimate | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ItineraryDetailResponse(ItinerarySummaryResponse):
    preferences_snapshot: dict = Field(default_factory=dict)
    weather_summary: dict | None = None
    recommendations: dict | None = None
    generation_metadata: dict = Field(default_factory=dict)
    days: list[ItineraryDayResponse] = Field(default_factory=list)


class ItineraryListResponse(ResponseModel):
    items: list[ItinerarySummaryResponse]
    total: int
    limit: int
    offset: int


class ItineraryActivityInput(StrictModel):
    place_id: str | None = Field(default=None, max_length=512)
    name: str = Field(min_length=1, max_length=200)
    category: ActivityCategory = ActivityCategory.OTHER
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_time: str | None = None
    end_time: str | None = None
    estimated_cost: float = Field(default=0, ge=0, le=1_000_000_000)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("start_time", "end_time")
    @classmethod
    def _valid_time(cls, value: str | None) -> str | None:
        if value is not None and not TIME_PATTERN.fullmatch(value):
            raise ValueError("Time must use 24-hour HH:MM format")
        return value

    @model_validator(mode="after")
    def _valid_coordinates(self) -> "ItineraryActivityInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude are required together")
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ItineraryDayInput(StrictModel):
    day_number: int = Field(ge=1, le=60)
    date: date
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=2000)
    activities: list[ItineraryActivityInput] = Field(default_factory=list, max_length=12)


class ItineraryUpdateRequest(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    summary: str | None = Field(default=None, max_length=3000)
    status: ItineraryStatus | None = None
    total_budget: float | None = Field(default=None, gt=0, le=1_000_000_000_000)
    days: list[ItineraryDayInput] | None = Field(
        default=None, min_length=1, max_length=60
    )

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ItineraryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one itinerary field must be supplied")
        for field in ("title", "status", "total_budget", "days"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null; omit it to keep the current value")
        if self.days is not None:
            numbers = [day.day_number for day in self.days]
            if len(numbers) != len(set(numbers)):
                raise ValueError("day_number values must be unique")
            dates = [day.date for day in self.days]
            if len(dates) != len(set(dates)):
                raise ValueError("Day dates must be unique")
        return self
