"""User profile, preferences, and saved-destination schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.models.enums import AccommodationPreference, TransportationPreference
from app.schemas.common import ResponseModel, StrictModel


class ProfileResponse(ResponseModel):
    id: UUID
    email: str
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    date_of_birth: date | None = None
    preferred_currency: str = "USD"
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(StrictModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    avatar_url: str | None = Field(default=None, max_length=2048)
    date_of_birth: date | None = None
    preferred_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("preferred_currency")
    @classmethod
    def _currency_upper(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("date_of_birth")
    @classmethod
    def _not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ProfileUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be supplied")
        return self


class TravelPreferencesInput(StrictModel):
    home_city: str | None = Field(default=None, max_length=160)
    interests: list[str] = Field(default_factory=list, max_length=20)
    activity_preferences: list[str] = Field(default_factory=list, max_length=20)
    accommodation_preference: AccommodationPreference = AccommodationPreference.MIDRANGE_HOTEL
    transportation_preference: TransportationPreference = TransportationPreference.MIXED
    budget_level: Literal["economy", "moderate", "premium"] | None = None
    dietary_preferences: list[str] = Field(default_factory=list, max_length=20)
    accessibility_needs: str | None = Field(default=None, max_length=500)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("interests", "activity_preferences", "dietary_preferences")
    @classmethod
    def _clean_list(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = value.strip()
            if item and item not in cleaned:
                cleaned.append(item[:80])
        return cleaned


class TravelPreferencesResponse(ResponseModel):
    user_id: UUID
    home_city: str | None = None
    interests: list[str] = Field(default_factory=list)
    activity_preferences: list[str] = Field(default_factory=list)
    accommodation_preference: AccommodationPreference
    transportation_preference: TransportationPreference
    budget_level: str | None = None
    dietary_preferences: list[str] = Field(default_factory=list)
    accessibility_needs: str | None = None
    currency: str
    created_at: datetime
    updated_at: datetime


class SavedDestinationCreate(StrictModel):
    place_id: str = Field(min_length=3, max_length=512)
    notes: str | None = Field(default=None, max_length=500)


class SavedDestinationResponse(ResponseModel):
    id: UUID
    user_id: UUID
    place_id: str
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    notes: str | None = None
    created_at: datetime


class SavedDestinationList(ResponseModel):
    items: list[SavedDestinationResponse]
    total: int


class RegisterProfileInput(StrictModel):
    """Internal helper schema kept for typing clarity."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
