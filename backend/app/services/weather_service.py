"""OpenWeather integration with explicit forecast-horizon honesty and caching."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import (
    ExternalServiceError,
    ExternalServiceTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.models.enums import WeatherUnits
from app.utils.cache import AsyncTTLCache

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


class OpenWeatherService:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.openweather_timeout_seconds)
        )
        self._cache = AsyncTTLCache(settings.weather_cache_ttl_seconds)
        # Place names are extremely stable; keep geocoding results much longer.
        self._geocode_cache = AsyncTTLCache(
            settings.weather_geocode_cache_ttl_seconds or settings.weather_cache_ttl_seconds
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.weather_key)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _require_key(self) -> str:
        key = self._settings.weather_key
        if not key:
            raise ServiceUnavailableError(
                "OpenWeather is not configured. Set OPENWEATHER_API_KEY."
            )
        return key

    async def _get(self, url: str, params: dict[str, Any], action: str) -> Any:
        try:
            response = await self._client.get(
                url,
                params=params,
                timeout=self._settings.openweather_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ExternalServiceTimeoutError(
                f"OpenWeather {action} timed out. Please try again."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "OpenWeather network failure during %s: %s", action, type(exc).__name__
            )
            raise ExternalServiceError("OpenWeather is currently unreachable.") from exc

        if response.status_code == 404:
            raise NotFoundError("OpenWeather could not find that destination.")
        if response.status_code == 401:
            raise ExternalServiceError(
                "OpenWeather rejected the configured API key."
            )
        if response.status_code == 429:
            raise ExternalServiceError(
                "OpenWeather rate limit reached. Please try again later."
            )
        if response.status_code >= 400:
            logger.warning(
                "OpenWeather %s failed with status %s", action, response.status_code
            )
            raise ExternalServiceError(
                f"OpenWeather {action} could not complete the request.",
                details={"upstream_status": response.status_code},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError("OpenWeather returned malformed JSON.") from exc
        return payload

    async def _geocode(self, destination: str) -> dict[str, Any]:
        cache_key = destination.strip().casefold()

        async def fetch() -> dict[str, Any]:
            key = self._require_key()
            payload = await self._get(
                GEOCODE_URL,
                {"q": destination, "limit": 1, "appid": key},
                "geocoding",
            )
            # The OpenWeather geocoding endpoint returns a JSON array.
            results = payload if isinstance(payload, list) else payload.get("results")
            if not results:
                raise NotFoundError(
                    f"OpenWeather could not geocode '{destination}'."
                )
            first = results[0]
            if (
                not isinstance(first, dict)
                or first.get("lat") is None
                or first.get("lon") is None
            ):
                raise ExternalServiceError(
                    "OpenWeather returned incomplete geocoding data."
                )
            return {
                "name": first.get("name") or destination,
                "country": first.get("country"),
                "state": first.get("state"),
                "latitude": float(first["lat"]),
                "longitude": float(first["lon"]),
            }

        return await self._geocode_cache.get_or_set(cache_key, fetch)

    async def _fetch_raw(
        self,
        latitude: float,
        longitude: float,
        units: WeatherUnits,
    ) -> dict[str, Any]:
        key = self._require_key()
        cache_key = (round(latitude, 4), round(longitude, 4), units.value)
        return await self._cache.get_or_set(
            cache_key,
            lambda: self._fetch_current_and_forecast(latitude, longitude, units, key),
        )

    async def _fetch_current_and_forecast(
        self,
        latitude: float,
        longitude: float,
        units: WeatherUnits,
        key: str,
    ) -> dict[str, Any]:
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": key,
            "units": units.value,
        }
        current_task = self._get(CURRENT_URL, params, "current weather")
        forecast_task = self._get(FORECAST_URL, params, "forecast")
        current_result, forecast_result = await asyncio.gather(
            current_task, forecast_task, return_exceptions=True
        )
        if isinstance(current_result, BaseException):
            raise current_result
        forecast_payload: dict[str, Any]
        forecast_error: str | None = None
        if isinstance(forecast_result, BaseException):
            logger.warning(
                "OpenWeather forecast unavailable: %s", type(forecast_result).__name__
            )
            forecast_payload = {}
            forecast_error = "Forecast data is temporarily unavailable."
        else:
            forecast_payload = forecast_result
        return {
            "current": current_result,
            "forecast": forecast_payload,
            "forecast_error": forecast_error,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _condition(raw: dict[str, Any]) -> dict[str, str | None]:
        weather = raw.get("weather") if isinstance(raw.get("weather"), list) else []
        first = weather[0] if weather and isinstance(weather[0], dict) else {}
        return {
            "main": str(first.get("main") or "Unknown"),
            "description": str(first.get("description") or "").capitalize(),
            "icon": first.get("icon"),
        }

    @staticmethod
    def _timestamp(value: Any) -> datetime | None:
        if not isinstance(value, (int, float)):
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc)

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalise_current(self, payload: dict[str, Any], units: WeatherUnits) -> dict[str, Any]:
        main = payload.get("main") if isinstance(payload.get("main"), dict) else {}
        wind = payload.get("wind") if isinstance(payload.get("wind"), dict) else {}
        sys_data = payload.get("sys") if isinstance(payload.get("sys"), dict) else {}
        return {
            "observed_at": self._timestamp(payload.get("dt")) or datetime.now(timezone.utc),
            "temperature": round(self._number(main.get("temp")), 1),
            "feels_like": round(self._number(main.get("feels_like")), 1),
            "temp_min": round(self._number(main.get("temp_min")), 1),
            "temp_max": round(self._number(main.get("temp_max")), 1),
            "humidity": int(self._number(main.get("humidity"))),
            "pressure": int(self._number(main.get("pressure"))),
            "wind_speed": round(self._number(wind.get("speed")), 2),
            "wind_degrees": int(self._number(wind.get("deg"))) if wind.get("deg") else None,
            "condition": self._condition(payload),
            "sunrise": self._timestamp(sys_data.get("sunrise")),
            "sunset": self._timestamp(sys_data.get("sunset")),
            "units": units,
        }

    @staticmethod
    def _local_date(timestamp: Any, offset_seconds: int) -> date | None:
        if not isinstance(timestamp, (int, float)):
            return None
        return datetime.fromtimestamp(timestamp + offset_seconds, tz=timezone.utc).date()

    def _aggregate_forecast(
        self,
        payload: dict[str, Any],
        units: WeatherUnits,
        offset_seconds: int,
    ) -> list[dict[str, Any]]:
        items = payload.get("list") if isinstance(payload.get("list"), list) else []
        grouped: dict[date, list[dict[str, Any]]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            local_date = self._local_date(item.get("dt"), offset_seconds)
            if local_date is None:
                continue
            grouped.setdefault(local_date, []).append(item)

        forecast: list[dict[str, Any]] = []
        symbol = "°C" if units == WeatherUnits.METRIC else "°F"
        for day_date in sorted(grouped):
            day_items = grouped[day_date]
            values: list[float] = []
            mins: list[float] = []
            maxs: list[float] = []
            humidities: list[float] = []
            pops: list[float] = []
            condition_counts: Counter[str] = Counter()
            descriptions: dict[str, str] = {}
            for item in day_items:
                main = item.get("main") if isinstance(item.get("main"), dict) else {}
                values.append(self._number(main.get("temp")))
                mins.append(self._number(main.get("temp_min")))
                maxs.append(self._number(main.get("temp_max")))
                humidities.append(self._number(main.get("humidity")))
                pops.append(self._number(item.get("pop")))
                condition = self._condition(item)
                main_name = str(condition["main"])
                condition_counts[main_name] += 1
                descriptions.setdefault(main_name, str(condition["description"] or main_name))
            dominant = condition_counts.most_common(1)[0][0] if condition_counts else "Unknown"
            temp_min = round(min(mins or values or [0]), 1)
            temp_max = round(max(maxs or values or [0]), 1)
            average = round(sum(values) / len(values), 1) if values else 0.0
            humidity = int(sum(humidities) / len(humidities)) if humidities else 0
            pop = round(max(pops) * 100) if pops else 0
            forecast.append(
                {
                    "date": day_date,
                    "temp_min": temp_min,
                    "temp_max": temp_max,
                    "average_temperature": average,
                    "humidity": humidity,
                    "precipitation_probability": float(pop),
                    "condition": {
                        "main": dominant,
                        "description": descriptions.get(dominant, dominant),
                        "icon": None,
                    },
                    "summary": (
                        f"{descriptions.get(dominant, dominant)}; {temp_min}{symbol} to "
                        f"{temp_max}{symbol}; up to {pop}% precipitation probability."
                    ),
                }
            )
        return forecast

    @staticmethod
    def _suggestions(
        current: dict[str, Any],
        forecast: list[dict[str, Any]],
        units: WeatherUnits,
        covers_dates: bool | None,
    ) -> list[str]:
        suggestions: list[str] = []
        conditions = [str(current["condition"]["main"]).lower()]
        conditions.extend(str(day["condition"]["main"]).lower() for day in forecast)
        if any(
            word in condition
            for condition in conditions
            for word in ("rain", "drizzle", "thunderstorm")
        ):
            suggestions.append(
                "Rain is possible: carry a compact umbrella or rain jacket and keep an indoor "
                "museum or cafe as a backup."
            )
        if any("snow" in condition for condition in conditions):
            suggestions.append(
                "Snow is possible: check road and transit status before leaving and allow extra "
                "travel time."
            )
        temperature = float(current["temperature"])
        hot = 32 if units == WeatherUnits.METRIC else 90
        cold = 5 if units == WeatherUnits.METRIC else 41
        if temperature >= hot:
            suggestions.append(
                "It is hot: schedule outdoor sightseeing early or late, carry water, and plan "
                "shaded breaks."
            )
        if temperature <= cold:
            suggestions.append(
                "It is cold: pack warm layers and check whether attractions have indoor waiting "
                "areas."
            )
        if current["wind_speed"] >= (10 if units == WeatherUnits.METRIC else 22):
            suggestions.append(
                "Windy conditions are reported: secure loose items and avoid exposed viewpoints."
            )
        if any(str(day["condition"]["main"]).lower() == "clear" for day in forecast):
            suggestions.append(
                "Clear periods are forecast: good windows for walking tours, parks, and viewpoints."
            )
        if covers_dates is False:
            suggestions.append(
                "The available forecast does not yet cover every travel date. Recheck closer to "
                "departure; do not treat this as a final weather guarantee."
            )
        if not suggestions:
            suggestions.append(
                "Weather looks broadly manageable. Recheck the forecast 24-48 hours before each "
                "outdoor activity."
            )
        return suggestions

    async def get_weather(
        self,
        destination: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        units: WeatherUnits = WeatherUnits.METRIC,
    ) -> dict[str, Any]:
        if start_date and end_date and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        location = await self._geocode(destination)
        return await self._weather_for_location(
            name=str(location["name"]),
            country=location.get("country"),
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
            start_date=start_date,
            end_date=end_date,
            units=units,
        )

    async def get_weather_for_coordinates(
        self,
        *,
        name: str,
        country: str | None = None,
        latitude: float,
        longitude: float,
        start_date: date | None = None,
        end_date: date | None = None,
        units: WeatherUnits = WeatherUnits.METRIC,
    ) -> dict[str, Any]:
        return await self._weather_for_location(
            name=name,
            country=country,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            units=units,
        )

    async def _weather_for_location(
        self,
        *,
        name: str,
        country: str | None,
        latitude: float,
        longitude: float,
        start_date: date | None,
        end_date: date | None,
        units: WeatherUnits,
    ) -> dict[str, Any]:
        raw = await self._fetch_raw(latitude, longitude, units)
        current_payload = raw["current"]
        forecast_payload = raw["forecast"]
        offset = 0
        if isinstance(forecast_payload, dict) and isinstance(forecast_payload.get("city"), dict):
            offset = int(forecast_payload["city"].get("timezone") or 0)
        current = self._normalise_current(current_payload, units)
        forecast = self._aggregate_forecast(forecast_payload, units, offset)
        available_dates = {day["date"] for day in forecast}
        covers: bool | None = None
        if start_date and end_date:
            requested = {
                date.fromordinal(ordinal)
                for ordinal in range(start_date.toordinal(), end_date.toordinal() + 1)
            }
            covers = bool(forecast) and requested.issubset(available_dates)
            overlapping = [day for day in forecast if start_date <= day["date"] <= end_date]
            if overlapping:
                forecast = overlapping
        suggestions = self._suggestions(current, forecast, units, covers)
        if raw.get("forecast_error"):
            suggestions.append(str(raw["forecast_error"]))
        return {
            "destination": name,
            "country": country,
            "latitude": latitude,
            "longitude": longitude,
            "units": units,
            "current": current,
            "forecast": forecast,
            "requested_start_date": start_date,
            "requested_end_date": end_date,
            "forecast_covers_requested_dates": covers,
            "suggestions": suggestions,
            "source": "OpenWeather API",
            "disclaimer": (
                "Current conditions are the latest observation returned by OpenWeather. "
                "Forecast data covers the provider's available horizon only and is not a "
                "guarantee of future weather."
            ),
            "fetched_at": datetime.fromisoformat(raw["fetched_at"]),
            "attribution": "Weather data by OpenWeather",
        }
