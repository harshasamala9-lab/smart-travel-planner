"""User-submitted review and rating schemas.

Reviews are independent of Google's ratings and are not verified visit records.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ResponseModel, StrictModel


class ReviewCreate(StrictModel):
    place_id: str = Field(min_length=3, max_length=512)
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=160)
    comment: str | None = Field(default=None, max_length=2000)
    visited_on: date | None = None

    @field_validator("visited_on")
    @classmethod
    def _not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("visited_on cannot be in the future")
        return value


class ReviewUpdate(StrictModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = Field(default=None, max_length=160)
    comment: str | None = Field(default=None, max_length=2000)
    visited_on: date | None = None

    @field_validator("rating")
    @classmethod
    def _rating_cannot_be_cleared(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("rating cannot be null; omit it to keep the current rating")
        return value

    @field_validator("visited_on")
    @classmethod
    def _not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("visited_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ReviewUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one review field must be supplied")
        return self


class ReviewResponse(ResponseModel):
    id: UUID
    place_id: str
    place_name: str
    rating: int
    title: str | None = None
    comment: str | None = None
    visited_on: date | None = None
    reviewer_name: str | None = None
    is_own: bool = False
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(ResponseModel):
    items: list[ReviewResponse]
    total: int
    limit: int
    offset: int
    average_rating: float | None = None
    disclaimer: str = (
        "Reviews are submitted by users. They are not verified visits and are "
        "separate from Google's place ratings."
    )
