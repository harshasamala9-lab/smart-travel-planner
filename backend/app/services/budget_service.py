"""Transparent budget estimation.

All figures are planning estimates derived from configurable average rates plus
AI-estimated activity costs. They are never presented as verified live prices.
"""

from __future__ import annotations

import math
from typing import Any

from app.config import Settings
from app.core.exceptions import ValidationAppError
from app.models.enums import AccommodationPreference, TransportationPreference

DEFAULT_BUDGET_RATES: dict[str, dict[str, Any]] = {
    "USD": {
        "lodging": {
            "none": 0,
            "hostel": 30,
            "budget_hotel": 70,
            "midrange_hotel": 150,
            "luxury_hotel": 350,
            "apartment": 120,
            "homestay": 60,
        },
        "food_per_person_per_day": 45,
        "local_transport_per_person_per_day": 20,
        "other_buffer_percent": 8,
    },
    "INR": {
        "lodging": {
            "none": 0,
            "hostel": 1_200,
            "budget_hotel": 2_500,
            "midrange_hotel": 5_000,
            "luxury_hotel": 12_000,
            "apartment": 4_500,
            "homestay": 2_000,
        },
        "food_per_person_per_day": 1_200,
        "local_transport_per_person_per_day": 600,
        "other_buffer_percent": 8,
    },
    "EUR": {
        "lodging": {
            "none": 0,
            "hostel": 28,
            "budget_hotel": 65,
            "midrange_hotel": 140,
            "luxury_hotel": 320,
            "apartment": 110,
            "homestay": 55,
        },
        "food_per_person_per_day": 42,
        "local_transport_per_person_per_day": 18,
        "other_buffer_percent": 8,
    },
    "GBP": {
        "lodging": {
            "none": 0,
            "hostel": 25,
            "budget_hotel": 60,
            "midrange_hotel": 130,
            "luxury_hotel": 300,
            "apartment": 100,
            "homestay": 50,
        },
        "food_per_person_per_day": 38,
        "local_transport_per_person_per_day": 15,
        "other_buffer_percent": 8,
    },
    "AED": {
        "lodging": {
            "none": 0,
            "hostel": 100,
            "budget_hotel": 250,
            "midrange_hotel": 500,
            "luxury_hotel": 1_200,
            "apartment": 450,
            "homestay": 200,
        },
        "food_per_person_per_day": 150,
        "local_transport_per_person_per_day": 60,
        "other_buffer_percent": 8,
    },
    "AUD": {
        "lodging": {
            "none": 0,
            "hostel": 45,
            "budget_hotel": 100,
            "midrange_hotel": 220,
            "luxury_hotel": 500,
            "apartment": 180,
            "homestay": 90,
        },
        "food_per_person_per_day": 65,
        "local_transport_per_person_per_day": 30,
        "other_buffer_percent": 8,
    },
    "CAD": {
        "lodging": {
            "none": 0,
            "hostel": 40,
            "budget_hotel": 90,
            "midrange_hotel": 200,
            "luxury_hotel": 450,
            "apartment": 160,
            "homestay": 80,
        },
        "food_per_person_per_day": 60,
        "local_transport_per_person_per_day": 28,
        "other_buffer_percent": 8,
    },
    "SGD": {
        "lodging": {
            "none": 0,
            "hostel": 35,
            "budget_hotel": 80,
            "midrange_hotel": 180,
            "luxury_hotel": 400,
            "apartment": 140,
            "homestay": 70,
        },
        "food_per_person_per_day": 55,
        "local_transport_per_person_per_day": 25,
        "other_buffer_percent": 8,
    },
    "JPY": {
        "lodging": {
            "none": 0,
            "hostel": 3_000,
            "budget_hotel": 7_000,
            "midrange_hotel": 15_000,
            "luxury_hotel": 35_000,
            "apartment": 12_000,
            "homestay": 6_000,
        },
        "food_per_person_per_day": 4_000,
        "local_transport_per_person_per_day": 1_500,
        "other_buffer_percent": 8,
    },
    "THB": {
        "lodging": {
            "none": 0,
            "hostel": 400,
            "budget_hotel": 900,
            "midrange_hotel": 2_000,
            "luxury_hotel": 5_000,
            "apartment": 1_800,
            "homestay": 800,
        },
        "food_per_person_per_day": 600,
        "local_transport_per_person_per_day": 250,
        "other_buffer_percent": 8,
    },
    "CNY": {
        "lodging": {
            "none": 0,
            "hostel": 150,
            "budget_hotel": 350,
            "midrange_hotel": 750,
            "luxury_hotel": 1_800,
            "apartment": 600,
            "homestay": 300,
        },
        "food_per_person_per_day": 250,
        "local_transport_per_person_per_day": 100,
        "other_buffer_percent": 8,
    },
    "CHF": {
        "lodging": {
            "none": 0,
            "hostel": 35,
            "budget_hotel": 80,
            "midrange_hotel": 170,
            "luxury_hotel": 380,
            "apartment": 130,
            "homestay": 70,
        },
        "food_per_person_per_day": 55,
        "local_transport_per_person_per_day": 22,
        "other_buffer_percent": 8,
    },
    "NZD": {
        "lodging": {
            "none": 0,
            "hostel": 45,
            "budget_hotel": 100,
            "midrange_hotel": 220,
            "luxury_hotel": 500,
            "apartment": 180,
            "homestay": 90,
        },
        "food_per_person_per_day": 65,
        "local_transport_per_person_per_day": 30,
        "other_buffer_percent": 8,
    },
    "MYR": {
        "lodging": {
            "none": 0,
            "hostel": 60,
            "budget_hotel": 150,
            "midrange_hotel": 300,
            "luxury_hotel": 700,
            "apartment": 250,
            "homestay": 120,
        },
        "food_per_person_per_day": 80,
        "local_transport_per_person_per_day": 30,
        "other_buffer_percent": 8,
    },
    "IDR": {
        "lodging": {
            "none": 0,
            "hostel": 150_000,
            "budget_hotel": 350_000,
            "midrange_hotel": 750_000,
            "luxury_hotel": 1_800_000,
            "apartment": 600_000,
            "homestay": 300_000,
        },
        "food_per_person_per_day": 200_000,
        "local_transport_per_person_per_day": 75_000,
        "other_buffer_percent": 8,
    },
    "KRW": {
        "lodging": {
            "none": 0,
            "hostel": 30_000,
            "budget_hotel": 70_000,
            "midrange_hotel": 150_000,
            "luxury_hotel": 350_000,
            "apartment": 120_000,
            "homestay": 60_000,
        },
        "food_per_person_per_day": 45_000,
        "local_transport_per_person_per_day": 15_000,
        "other_buffer_percent": 8,
    },
}

TRANSPORT_COST_MULTIPLIERS: dict[str, float] = {
    "none": 0.0,
    "walking": 0.2,
    "public_transport": 1.0,
    "mixed": 1.1,
    "taxi_rideshare": 1.8,
    "rental_car": 2.2,
}


class BudgetService:
    def __init__(self, settings: Settings) -> None:
        self._rates = self._load_rates(settings)

    @staticmethod
    def _load_rates(settings: Settings) -> dict[str, dict[str, Any]]:
        rates: dict[str, dict[str, Any]] = {
            currency: {
                **profile,
                "lodging": dict(profile["lodging"]),
            }
            for currency, profile in DEFAULT_BUDGET_RATES.items()
        }
        overrides = settings.budget_rates()
        for currency, profile in overrides.items():
            code = currency.upper()
            if not isinstance(profile, dict):
                raise ValueError(f"Budget override for {code} must be an object")
            base = rates.setdefault(code, {})
            for key, value in profile.items():
                if key == "lodging" and isinstance(value, dict):
                    base.setdefault("lodging", {}).update(value)
                else:
                    base[key] = value
        for code, profile in rates.items():
            if len(code) != 3 or not code.isalpha() or code != code.upper():
                raise ValueError(
                    f"Budget profile code {code!r} must be a 3-letter uppercase "
                    "ISO 4217 currency code"
                )
            required = (
                "lodging",
                "food_per_person_per_day",
                "local_transport_per_person_per_day",
                "other_buffer_percent",
            )
            missing = [key for key in required if key not in profile]
            if missing:
                raise ValueError(f"Budget profile {code} is missing: {', '.join(missing)}")
            lodging = profile["lodging"]
            if not isinstance(lodging, dict):
                raise ValueError(f"Budget profile {code} lodging must be an object")
            for key in (
                "food_per_person_per_day",
                "local_transport_per_person_per_day",
                "other_buffer_percent",
            ):
                BudgetService._require_non_negative_number(code, key, profile[key])
            for preference, rate in lodging.items():
                BudgetService._require_non_negative_number(
                    code, f"lodging.{preference}", rate
                )
        return rates

    @staticmethod
    def _require_non_negative_number(currency: str, field: str, value: Any) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise ValueError(
                f"Budget profile {currency} field {field} must be a finite, "
                "non-negative number"
            )

    @property
    def supported_currencies(self) -> list[str]:
        return sorted(self._rates)

    def estimate(
        self,
        *,
        currency: str,
        travellers: int,
        day_count: int,
        total_budget: float,
        accommodation_preference: AccommodationPreference,
        transportation_preference: TransportationPreference,
        activity_costs_per_person: list[float],
    ) -> dict[str, Any]:
        code = currency.upper()
        profile = self._rates.get(code)
        if profile is None:
            raise ValidationAppError(
                f"Budget estimation is not configured for currency {code}.",
                details={"supported_currencies": self.supported_currencies},
            )
        if travellers < 1 or day_count < 1:
            raise ValueError("travellers and day_count must be at least 1")

        nights = max(0, day_count - 1)
        rooms = 0
        if accommodation_preference != AccommodationPreference.NONE and nights > 0:
            rooms = math.ceil(travellers / 2)

        lodging_rates = profile["lodging"]
        nightly_rate = float(lodging_rates.get(accommodation_preference.value, 0))
        accommodation = nightly_rate * rooms * nights

        food_rate = float(profile["food_per_person_per_day"])
        food = food_rate * travellers * day_count

        transport_base = float(profile["local_transport_per_person_per_day"])
        transport_multiplier = TRANSPORT_COST_MULTIPLIERS.get(
            transportation_preference.value, 1.0
        )
        transportation = transport_base * transport_multiplier * travellers * day_count

        activities_per_person = sum(max(0.0, float(cost)) for cost in activity_costs_per_person)
        activities = activities_per_person * travellers

        subtotal = accommodation + food + transportation + activities
        buffer_percent = float(profile["other_buffer_percent"])
        other = subtotal * (buffer_percent / 100)
        total = round(subtotal + other, 2)
        per_person = round(total / travellers, 2)
        remaining = round(total_budget - total, 2)
        over_budget = remaining < 0
        within_budget = not over_budget
        utilization = round((total / total_budget) * 100, 1) if total_budget > 0 else 0.0

        warning: str | None = None
        if over_budget:
            warning = (
                f"Estimated cost exceeds the total budget by "
                f"{code} {abs(remaining):,.2f}. Consider a cheaper accommodation "
                "category, fewer paid activities, or a longer budget review."
            )
        elif utilization >= 90:
            warning = (
                f"Estimated cost uses {utilization:.1f}% of the total budget, leaving "
                "very little contingency."
            )

        transport_note = (
            "Local transport only; intercity flights/trains and airport transfers "
            "are not included."
        )
        assumptions = [
            (
                f"Accommodation: {nights} night(s), {rooms} room(s) at an average "
                f"{code} {nightly_rate:,.2f}/room/night for "
                f"{accommodation_preference.value.replace('_', ' ')}."
            ),
            (
                f"Food: {code} {food_rate:,.2f} per traveller per day for "
                f"{travellers} traveller(s) over {day_count} day(s)."
            ),
            (
                f"Transport: {code} {transport_base:,.2f} base per traveller per day "
                f"with a {transport_multiplier:g}x preference multiplier. {transport_note}"
            ),
            (
                "Activities: per-person costs proposed by the planner; entrance fees, "
                "availability, and opening hours must be verified before booking."
            ),
            (
                f"Other: {buffer_percent:g}% contingency buffer for incidentals and "
                "price variation."
            ),
        ]

        return {
            "currency": code,
            "line_items": {
                "transportation": round(transportation, 2),
                "accommodation": round(accommodation, 2),
                "food": round(food, 2),
                "activities": round(activities, 2),
                "other": round(other, 2),
            },
            "total": total,
            "per_person": per_person,
            "total_budget": round(float(total_budget), 2),
            "remaining": remaining,
            "over_budget": over_budget,
            "within_budget": within_budget,
            "utilization_percent": utilization,
            "warning": warning,
            "accommodation_nights": nights,
            "rooms": rooms,
            "cost_type": "estimated",
            "assumptions": assumptions,
            "disclaimer": (
                "All amounts are planning estimates calculated from configurable average "
                "rates and AI-estimated activity costs. They are not verified live prices."
            ),
        }
