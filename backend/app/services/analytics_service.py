"""Currency-safe travel analytics computed from persisted user data."""

from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from app.database.repositories import AnalyticsRepository, ReviewRepository


class AnalyticsService:
    def __init__(
        self,
        *,
        analytics_repository: AnalyticsRepository,
        review_repository: ReviewRepository,
    ) -> None:
        self._analytics = analytics_repository
        self._reviews = review_repository

    @staticmethod
    def _date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) else default

    async def build(self, user_id: uuid.UUID) -> dict[str, Any]:
        itineraries = await self._analytics.itinerary_rows(user_id)
        activities = await self._analytics.activity_rows(user_id)
        review_count = await self._reviews.count_for_user(user_id)
        today = date.today()

        status_counts = Counter(str(item.get("status") or "generated") for item in itineraries)
        upcoming = active = completed = 0
        destination_counts: Counter[tuple[str, str | None]] = Counter()
        monthly_counts: Counter[str] = Counter()
        currency_totals: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "itinerary_count": 0,
                "planned_budget": 0.0,
                "estimated_cost": 0.0,
                "line_items": defaultdict(float),
            }
        )

        for item in itineraries:
            start = self._date(item.get("start_date"))
            end = self._date(item.get("end_date"))
            if start and end:
                if start > today:
                    upcoming += 1
                elif end < today:
                    completed += 1
                else:
                    active += 1

            name = str(item.get("destination_name") or "Unknown")
            place_id = item.get("destination_place_id")
            destination_counts[(name, str(place_id) if place_id else None)] += 1

            created = item.get("created_at")
            if isinstance(created, str) and len(created) >= 7:
                monthly_counts[created[:7]] += 1

            currency = str(item.get("currency") or "USD").upper()
            totals = currency_totals[currency]
            totals["itinerary_count"] += 1
            totals["planned_budget"] += self._number(item.get("total_budget"))
            estimate = item.get("budget_estimate")
            if isinstance(estimate, dict):
                totals["estimated_cost"] += self._number(estimate.get("total"))
                line_items = estimate.get("line_items")
                if isinstance(line_items, dict):
                    for key, value in line_items.items():
                        totals["line_items"][str(key)] += self._number(value)

        activity_counts: Counter[str] = Counter()
        activity_amounts: dict[str, float] = defaultdict(float)
        for activity in activities:
            category = str(activity.get("category") or "other")
            activity_counts[category] += 1
            currency = str(activity.get("currency") or "USD").upper()
            try:
                travellers = max(1, int(self._number(activity.get("travellers"), 1)))
            except (TypeError, ValueError, OverflowError):
                travellers = 1
            amount = self._number(activity.get("estimated_cost")) * travellers
            activity_amounts[currency] += amount

        currencies = []
        for code in sorted(currency_totals):
            totals = currency_totals[code]
            currencies.append(
                {
                    "currency": code,
                    "itinerary_count": int(totals["itinerary_count"]),
                    "planned_budget": round(float(totals["planned_budget"]), 2),
                    "estimated_cost": round(float(totals["estimated_cost"]), 2),
                    "activity_estimate": round(activity_amounts.get(code, 0.0), 2),
                    "line_items": {
                        key: round(float(value), 2)
                        for key, value in sorted(totals["line_items"].items())
                    },
                }
            )

        top_destinations = [
            {
                "destination_name": name,
                "destination_place_id": place_id,
                "trip_count": count,
            }
            for (name, place_id), count in destination_counts.most_common(5)
        ]
        monthly_itineraries = [
            {"month": month, "trip_count": count}
            for month, count in sorted(monthly_counts.items())[-12:]
        ]

        return {
            "total_itineraries": len(itineraries),
            "upcoming_trips": upcoming,
            "active_trips": active,
            "completed_trips": completed,
            "draft_trips": status_counts.get("draft", 0),
            "archived_trips": status_counts.get("archived", 0),
            "reviews_count": review_count,
            "currencies": currencies,
            "top_destinations": top_destinations,
            "monthly_itineraries": monthly_itineraries,
            "activity_counts": dict(sorted(activity_counts.items())),
            "generated_at": datetime.now(timezone.utc),
            "notes": [
                "Currencies are reported separately and are never summed or converted.",
                "Budget and activity amounts are planning estimates, not live prices.",
                "Status and monthly counts are based on saved itinerary records.",
            ],
            "metadata": {
                "sources": ["Neon Postgres", "Google Places", "Google Routes", "OpenWeather"],
                "itinerary_rows": len(itineraries),
                "activity_rows": len(activities),
            },
        }
