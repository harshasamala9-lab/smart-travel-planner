"""Shared enums used by schemas, services, and persistence."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum compatible with JSON and SQL."""


class ItineraryStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    SAVED = "saved"
    ARCHIVED = "archived"


class ActivityCategory(StrEnum):
    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    TRANSPORT = "transport"
    OTHER = "other"


class CostType(StrEnum):
    ESTIMATED = "estimated"
    VERIFIED = "verified"


class AccommodationPreference(StrEnum):
    NONE = "none"
    HOSTEL = "hostel"
    BUDGET_HOTEL = "budget_hotel"
    MIDRANGE_HOTEL = "midrange_hotel"
    LUXURY_HOTEL = "luxury_hotel"
    APARTMENT = "apartment"
    HOMESTAY = "homestay"


class TransportationPreference(StrEnum):
    NONE = "none"
    WALKING = "walking"
    PUBLIC_TRANSPORT = "public_transport"
    TAXI_RIDESHARE = "taxi_rideshare"
    RENTAL_CAR = "rental_car"
    MIXED = "mixed"


class TravelPace(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    PACKED = "packed"


class TravelMode(StrEnum):
    DRIVE = "DRIVE"
    WALK = "WALK"
    BICYCLE = "BICYCLE"
    TRANSIT = "TRANSIT"


class WeatherUnits(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"
