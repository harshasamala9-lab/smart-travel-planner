"""Internal structured-output schema used with the Gemini API.

The model may choose only place IDs supplied in the prompt. It never supplies
addresses, coordinates, opening hours, or verified prices for storage; the
backend enriches each item from Google Places.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.itineraries import TIME_PATTERN


class AIActivity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    place_id: str = Field(min_length=1, max_length=512)
    start_time: str
    end_time: str
    description: str = Field(min_length=1, max_length=1000)
    estimated_cost: float = Field(default=0, ge=0, le=1_000_000_000)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("start_time", "end_time")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        if not TIME_PATTERN.fullmatch(value):
            raise ValueError("Time must use HH:MM")
        return value

    @field_validator("end_time")
    @classmethod
    def _end_after_start(cls, value: str, info: object) -> str:
        start = getattr(info, "data", {}).get("start_time")
        if start and value <= start:
            raise ValueError("end_time must be after start_time")
        return value


class AIDay(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day_number: int = Field(ge=1, le=60)
    date: date
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=2000)
    activities: list[AIActivity] = Field(min_length=1, max_length=12)


class AIItinerary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=3000)
    recommended_hotel_place_id: str | None = Field(default=None, max_length=512)
    days: list[AIDay] = Field(min_length=1, max_length=60)
    tips: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("tips")
    @classmethod
    def _clean_tips(cls, values: list[str]) -> list[str]:
        return [value.strip()[:500] for value in values if value.strip()]
