"""Destination discovery and Google Maps route schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.models.enums import ActivityCategory, TravelMode
from app.schemas.common import ResponseModel, StrictModel


class PlaceSummary(ResponseModel):
    place_id: str
    name: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    price_level: str | None = None
    types: list[str] = Field(default_factory=list)
    category: ActivityCategory | None = None
    open_now: bool | None = None
    business_status: str | None = None
    google_maps_uri: str | None = None
    photo_names: list[str] = Field(default_factory=list)
    opening_hours: list[str] = Field(default_factory=list)
    # Travel-only curated metadata (None for live Google results).
    description: str | None = None
    country: str | None = None
    image_url: str | None = None
    image_alt: str | None = None
    image_credit: str | None = None
    best_time: str | None = None
    travel_type: str | None = None
    source: str | None = None


class PlaceDetails(PlaceSummary):
    website_uri: str | None = None
    national_phone_number: str | None = None
    editorial_summary: str | None = None
    current_opening_hours: list[str] = Field(default_factory=list)


class DestinationSearchResponse(ResponseModel):
    query: str
    items: list[PlaceSummary]
    count: int
    source: str = "Google Places API (New)"
    travel_only: bool = True
    suggestions: list[str] = Field(default_factory=list)
    message: str | None = None


class NearbyPlacesResponse(ResponseModel):
    place_id: str
    destination_name: str
    items: list[PlaceSummary]
    count: int
    radius_m: int
    included_types: list[str] = Field(default_factory=list)
    source: str = "Google Places API (New)"
    message: str | None = None


class RouteLocation(StrictModel):
    """Exactly one of place_id, address, or a latitude/longitude pair."""

    place_id: str | None = Field(default=None, max_length=512)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _one_location_mode(self) -> "RouteLocation":
        has_coords = self.latitude is not None and self.longitude is not None
        has_partial_coords = (self.latitude is None) != (self.longitude is None)
        modes = sum([bool(self.place_id), bool(self.address), has_coords])
        if has_partial_coords:
            raise ValueError("Both latitude and longitude are required")
        if modes != 1:
            raise ValueError("Provide exactly one of place_id, address, or latitude/longitude")
        return self


class ResolvedLocation(ResponseModel):
    name: str | None = None
    address: str | None = None
    latitude: float
    longitude: float
    place_id: str | None = None


class RouteStep(ResponseModel):
    instruction: str | None = None
    distance_meters: int | None = None
    duration_seconds: int | None = None


class RouteRequest(StrictModel):
    origin: RouteLocation
    destination: RouteLocation
    travel_mode: TravelMode = TravelMode.DRIVE
    include_steps: bool = False


class RouteResponse(ResponseModel):
    origin: ResolvedLocation
    destination: ResolvedLocation
    travel_mode: TravelMode
    distance_meters: int
    distance_km: float
    duration_seconds: int
    duration_minutes: float
    polyline: str | None = None
    steps: list[RouteStep] = Field(default_factory=list)
    source: str = "Google Routes API"
    calculated_at: datetime


class PlaceQuery(StrictModel):
    query: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)
    language: Literal["en"] | None = None
