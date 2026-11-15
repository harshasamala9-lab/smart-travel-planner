"""User reviews with Google Places verification and ownership rules."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.exceptions import ConflictError, NotFoundError
from app.database.repositories import ReviewRepository
from app.schemas.reviews import ReviewCreate, ReviewUpdate
from app.services.maps_service import GoogleMapsService


class ReviewService:
    def __init__(
        self,
        *,
        review_repository: ReviewRepository,
        maps_service: GoogleMapsService,
    ) -> None:
        self._reviews = review_repository
        self._maps = maps_service

    @staticmethod
    def _decorate(row: dict[str, Any], viewer_id: uuid.UUID) -> dict[str, Any]:
        result = dict(row)
        result["is_own"] = str(row.get("user_id")) == str(viewer_id)
        return result

    async def create(
        self,
        user_id: uuid.UUID,
        payload: ReviewCreate,
    ) -> dict[str, Any]:
        existing = await self._reviews.get_by_user_and_place(
            user_id, payload.place_id
        )
        if existing is not None:
            raise ConflictError(
                "You have already reviewed this place. Update your existing review instead."
            )
        place = await self._maps.get_place_details(payload.place_id)
        review = await self._reviews.create(
            user_id=user_id,
            place_id=payload.place_id,
            place_name=place["name"],
            rating=payload.rating,
            title=payload.title,
            comment=payload.comment,
            visited_on=payload.visited_on.isoformat() if payload.visited_on else None,
        )
        return self._decorate(review, user_id)

    async def list_for_place(
        self,
        viewer_id: uuid.UUID,
        place_id: str,
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        items, total, average = await self._reviews.list_for_place(
            place_id, limit=limit, offset=offset
        )
        return {
            "items": [self._decorate(item, viewer_id) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "average_rating": average,
        }

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        items, total = await self._reviews.list_for_user(
            user_id, limit=limit, offset=offset
        )
        return {
            "items": [self._decorate(item, user_id) for item in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def update(
        self,
        user_id: uuid.UUID,
        review_id: uuid.UUID,
        payload: ReviewUpdate,
    ) -> dict[str, Any]:
        values = payload.model_dump(exclude_unset=True, mode="json")
        review = await self._reviews.update(user_id, review_id, values)
        if review is None:
            raise NotFoundError("Review not found.")
        return self._decorate(review, user_id)

    async def delete(self, user_id: uuid.UUID, review_id: uuid.UUID) -> None:
        deleted = await self._reviews.delete(user_id, review_id)
        if not deleted:
            raise NotFoundError("Review not found.")
