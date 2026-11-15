"""Expiring, hashed itinerary share links and public read-only projection."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.exceptions import NotFoundError
from app.database.repositories import ItineraryRepository, ItineraryShareRepository


class ShareService:
    def __init__(
        self,
        *,
        itinerary_repository: ItineraryRepository,
        share_repository: ItineraryShareRepository,
    ) -> None:
        self._itineraries = itinerary_repository
        self._shares = share_repository

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _expired(value: Any) -> bool:
        if not value:
            return False
        try:
            expires = datetime.fromisoformat(str(value))
        except ValueError:
            return True
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= datetime.now(timezone.utc)

    @staticmethod
    def public_projection(itinerary: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": itinerary["id"],
            "title": itinerary["title"],
            "summary": itinerary.get("summary"),
            "destination_name": itinerary["destination_name"],
            "destination_place_id": itinerary.get("destination_place_id"),
            "destination_address": itinerary.get("destination_address"),
            "destination_latitude": itinerary.get("destination_latitude"),
            "destination_longitude": itinerary.get("destination_longitude"),
            "start_date": itinerary["start_date"],
            "end_date": itinerary["end_date"],
            "travellers": itinerary["travellers"],
            "currency": itinerary["currency"],
            "status": itinerary["status"],
            "accommodation_preference": itinerary["accommodation_preference"],
            "transportation_preference": itinerary["transportation_preference"],
            "pace": itinerary["pace"],
            "interests": itinerary.get("interests") or [],
            "budget_estimate": itinerary.get("budget_estimate"),
            "warnings": itinerary.get("warnings") or [],
            "days": itinerary.get("days") or [],
            "recommendations": itinerary.get("recommendations"),
            "weather_summary": itinerary.get("weather_summary"),
        }

    async def create(
        self,
        user_id: uuid.UUID,
        itinerary_id: uuid.UUID,
        *,
        expires_in_days: int,
    ) -> dict[str, Any]:
        itinerary = await self._itineraries.get_for_user(user_id, itinerary_id)
        if itinerary is None:
            raise NotFoundError("Itinerary not found.")
        token = secrets.token_urlsafe(32)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        ).isoformat()
        share = await self._shares.create(
            itinerary_id=itinerary_id,
            user_id=user_id,
            token_hash=self._hash(token),
            expires_at=expires_at,
        )
        return {
            "id": share["id"],
            "itinerary_id": share["itinerary_id"],
            "token": token,
            "expires_at": share["expires_at"],
            "created_at": share["created_at"],
        }

    async def list_for_itinerary(
        self, user_id: uuid.UUID, itinerary_id: uuid.UUID
    ) -> dict[str, Any]:
        itinerary = await self._itineraries.get_for_user(
            user_id, itinerary_id, include_days=False
        )
        if itinerary is None:
            raise NotFoundError("Itinerary not found.")
        rows = await self._shares.list_for_itinerary(user_id, itinerary_id)
        items = [
            {
                "id": row["id"],
                "itinerary_id": row["itinerary_id"],
                "expires_at": row.get("expires_at"),
                "is_expired": self._expired(row.get("expires_at")),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        return {"items": items, "total": len(items)}

    async def revoke_all(self, user_id: uuid.UUID, itinerary_id: uuid.UUID) -> int:
        itinerary = await self._itineraries.get_for_user(
            user_id, itinerary_id, include_days=False
        )
        if itinerary is None:
            raise NotFoundError("Itinerary not found.")
        return await self._shares.revoke_all(user_id, itinerary_id)

    async def resolve(self, token: str) -> dict[str, Any]:
        share = await self._shares.get_active_by_hash(self._hash(token))
        if share is None or self._expired(share.get("expires_at")):
            raise NotFoundError("This share link is invalid, expired, or revoked.")
        itinerary = await self._itineraries.get_for_user(
            share["user_id"], share["itinerary_id"]
        )
        if itinerary is None:
            raise NotFoundError("This shared itinerary is no longer available.")
        return self.public_projection(itinerary)
