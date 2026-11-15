"""Interest-ranked destination recommendations using Google Places only."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import AppError, ExternalServiceError, NotFoundError
from app.models.enums import ActivityCategory
from app.schemas.recommendations import RecommendationRequest
from app.services.maps_service import GoogleMapsService
from app.utils.interests import (
    DEFAULT_ATTRACTION_TYPES,
    HOTEL_TYPES,
    RESTAURANT_TYPES,
    matched_interests,
    place_types_for_interests,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, maps_service: GoogleMapsService) -> None:
        self._maps = maps_service

    async def recommend(self, request: RecommendationRequest) -> dict[str, Any]:
        destination = await self._maps.resolve_destination(
            request.destination, request.destination_place_id
        )
        if destination.get("latitude") is None or destination.get("longitude") is None:
            raise ExternalServiceError("Destination coordinates are unavailable.")

        attraction_types = place_types_for_interests(
            request.interests, default=DEFAULT_ATTRACTION_TYPES
        )
        latitude = float(destination["latitude"])
        longitude = float(destination["longitude"])
        attraction_task = self._maps.nearby_places(
            latitude=latitude,
            longitude=longitude,
            included_types=attraction_types,
            limit=20,
            radius_m=request.radius_m,
            category=ActivityCategory.ATTRACTION,
        )
        restaurant_task = self._maps.nearby_places(
            latitude=latitude,
            longitude=longitude,
            included_types=RESTAURANT_TYPES,
            limit=20,
            radius_m=request.radius_m,
            category=ActivityCategory.RESTAURANT,
        )
        hotel_task = (
            self._maps.nearby_places(
                latitude=latitude,
                longitude=longitude,
                included_types=HOTEL_TYPES,
                limit=10,
                radius_m=request.radius_m,
                category=ActivityCategory.HOTEL,
            )
            if request.include_hotels
            else None
        )
        tasks: list[Any] = [attraction_task, restaurant_task]
        if hotel_task is not None:
            tasks.append(hotel_task)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        warnings: list[str] = []

        attractions = self._extract(results[0], "attractions", warnings)
        restaurants = self._extract(results[1], "restaurants", warnings)
        hotels = (
            self._extract(results[2], "hotels", warnings)
            if len(results) > 2
            else []
        )
        if not attractions and not restaurants and not hotels:
            raise NotFoundError(
                "No places were found for these interests. Try a broader interest or radius."
            )

        ranked_attractions = self._rank(
            attractions,
            request.interests,
            request.budget_level,
        )
        ranked_restaurants = self._rank(
            restaurants,
            request.interests,
            request.budget_level,
        )
        ranked_hotels = self._rank(
            hotels,
            request.interests,
            request.budget_level,
        )

        tips = [
            "Places are sourced from Google Places; ratings, price levels, and opening status "
            "can change. Confirm before booking.",
            "Distances and travel time should be checked with the Routes endpoint when "
            "sequencing several places.",
        ]
        if request.dietary_preferences:
            tips.append(
                "Dietary needs are not verified by Google Places. Contact each restaurant "
                "directly about ingredients and cross-contamination."
            )
        if request.interests:
            tips.append(
                "Interest matching is deterministic and based on Google place types; use your "
                "saved itinerary feedback to refine future suggestions."
            )

        return {
            "destination": destination["name"],
            "destination_place_id": destination.get("place_id"),
            "attractions": [item for item in ranked_attractions[: request.limit]],
            "restaurants": [item for item in ranked_restaurants[: request.limit]],
            "hotels": [item for item in ranked_hotels[: min(5, request.limit)]],
            "tips": tips,
            "warnings": warnings,
            "source": "Google Places API (New)",
            "ranking_method": (
                "Deterministic ranking using interest/type match, Google rating, review "
                "volume, price-level alignment, and current open status"
            ),
            "generated_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def _extract(
        result: Any,
        label: str,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if isinstance(result, BaseException):
            if isinstance(result, AppError):
                warnings.append(f"{label.capitalize()} unavailable: {result.message}")
            else:
                logger.warning(
                    "Recommendation %s lookup failed: %s",
                    label,
                    type(result).__name__,
                )
                warnings.append(f"{label.capitalize()} are temporarily unavailable.")
            return []
        return list(result or [])

    @staticmethod
    def _price_score(price_level: str | None, budget_level: str | None) -> float:
        if not budget_level or not price_level:
            return 0.0
        value = price_level.upper()
        economical = {"PRICE_LEVEL_INEXPENSIVE": 8, "PRICE_LEVEL_MODERATE": 3}
        moderate = {"PRICE_LEVEL_INEXPENSIVE": 4, "PRICE_LEVEL_MODERATE": 6}
        premium = {
            "PRICE_LEVEL_EXPENSIVE": 7,
            "PRICE_LEVEL_VERY_EXPENSIVE": 7,
            "PRICE_LEVEL_MODERATE": 2,
        }
        table = {"economy": economical, "moderate": moderate, "premium": premium}
        return float(table.get(budget_level, {}).get(value, -3))

    def _rank(
        self,
        places: list[dict[str, Any]],
        interests: list[str],
        budget_level: str | None,
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for place in places:
            rating = float(place.get("rating") or 0)
            reviews = int(place.get("user_rating_count") or 0)
            matches = matched_interests(place.get("types", []), interests)
            score = rating * 10 + math.log10(reviews + 1) * 4
            score += min(len(matches), 3) * 8
            score += self._price_score(place.get("price_level"), budget_level)
            if place.get("open_now") is True:
                score += 2
            reasons: list[str] = []
            if matches:
                reasons.append("matches your interest in " + ", ".join(matches))
            if rating:
                reasons.append(f"rated {rating:.1f}/5 on Google")
            if reviews:
                reasons.append(f"{reviews:,} Google reviews")
            if place.get("open_now") is True:
                reasons.append("currently reported open")
            if not reasons:
                reasons.append("popular place returned by Google Places")
            item = dict(place)
            item["score"] = round(score, 1)
            item["reason"] = "; ".join(reasons).capitalize() + "."
            ranked.append(item)
        return sorted(
            ranked,
            key=lambda item: (
                float(item.get("score") or 0),
                float(item.get("rating") or 0),
                int(item.get("user_rating_count") or 0),
            ),
            reverse=True,
        )
