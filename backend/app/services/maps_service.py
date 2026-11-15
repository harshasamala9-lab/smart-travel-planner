"""Google Maps Platform integration: Places (New), Geocoding, and Routes."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.core.exceptions import (
    ExternalServiceError,
    ExternalServiceTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.models.enums import ActivityCategory, TravelMode
from app.utils.cache import AsyncTTLCache

logger = logging.getLogger(__name__)

PLACES_BASE = "https://places.googleapis.com/v1"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

PLACE_SUMMARY_FIELDS = (
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.types",
    "places.businessStatus",
    "places.googleMapsUri",
    "places.editorialSummary.text",
    "places.currentOpeningHours.openNow",
    "places.regularOpeningHours.weekdayDescriptions",
    "places.photos.name",
)

PLACE_DETAIL_FIELDS = (
    "id",
    "displayName",
    "formattedAddress",
    "location",
    "rating",
    "userRatingCount",
    "priceLevel",
    "types",
    "businessStatus",
    "googleMapsUri",
    "currentOpeningHours.openNow",
    "currentOpeningHours.openNow",
    "currentOpeningHours.weekdayDescriptions",
    "regularOpeningHours.weekdayDescriptions",
    "photos.name",
    "websiteUri",
    "nationalPhoneNumber",
    "editorialSummary.text",
)

PHOTO_NAME_PATTERN = re.compile(r"^places/[A-Za-z0-9_-]+/photos/[A-Za-z0-9_-]+$")


class GoogleMapsService:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.google_maps_timeout_seconds),
            follow_redirects=True,
        )
        # Unbounded-entry, TTL-managed caches. Route responses have a shorter
        # TTL because traffic-aware durations go stale quickly.
        self._cache = AsyncTTLCache(settings.maps_cache_ttl_seconds)
        self._route_cache = AsyncTTLCache(settings.maps_route_cache_ttl_seconds)
        self._photo_cache = AsyncTTLCache(settings.maps_photo_cache_ttl_seconds)

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.maps_key)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _require_key(self) -> str:
        key = self._settings.maps_key
        if not key:
            raise ServiceUnavailableError(
                "Google Maps is not configured. Set GOOGLE_MAPS_API_KEY."
            )
        return key

    async def _request(
        self,
        method: str,
        url: str,
        *,
        action: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=self._settings.google_maps_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ExternalServiceTimeoutError(
                f"Google {action} timed out. Please try again."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Google Maps network failure during %s: %s", action, type(exc).__name__)
            raise ExternalServiceError(f"Google {action} is currently unreachable.") from exc

        if response.status_code >= 400:
            upstream_message = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    error = payload.get("error")
                    if isinstance(error, dict):
                        upstream_message = str(error.get("message") or "")[:300]
            except ValueError:
                pass
            if response.status_code == 404:
                raise NotFoundError("The requested place was not found.")
            logger.warning(
                "Google Maps %s failed with %s: %s",
                action,
                response.status_code,
                upstream_message,
            )
            raise ExternalServiceError(
                f"Google {action} could not complete the request.",
                details={"upstream_status": response.status_code},
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ExternalServiceError(f"Google {action} returned malformed JSON.") from exc

    def _place_headers(self, field_mask: str) -> dict[str, str]:
        return {
            "X-Goog-Api-Key": self._require_key(),
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _text(value: Any) -> str | None:
        if isinstance(value, dict):
            text = value.get("text")
            return str(text) if text else None
        return str(value) if value else None

    @staticmethod
    def _normalise_place(
        place: dict[str, Any],
        *,
        category: ActivityCategory | None = None,
    ) -> dict[str, Any]:
        location = place.get("location") if isinstance(place.get("location"), dict) else {}
        display_name = GoogleMapsService._text(place.get("displayName")) or "Unnamed place"
        photos = place.get("photos") if isinstance(place.get("photos"), list) else []
        photo_names = [
            str(photo["name"])
            for photo in photos
            if isinstance(photo, dict) and photo.get("name")
        ][:3]
        regular_hours = (
            place.get("regularOpeningHours")
            if isinstance(place.get("regularOpeningHours"), dict)
            else {}
        )
        current_hours = (
            place.get("currentOpeningHours")
            if isinstance(place.get("currentOpeningHours"), dict)
            else {}
        )
        raw_types = place.get("types") if isinstance(place.get("types"), list) else []
        return {
            "place_id": str(place.get("id") or ""),
            "name": display_name,
            "formatted_address": place.get("formattedAddress"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "rating": place.get("rating"),
            "user_rating_count": place.get("userRatingCount"),
            "price_level": place.get("priceLevel"),
            "types": [str(value) for value in raw_types],
            "category": category.value if category else None,
            "open_now": current_hours.get("openNow"),
            "business_status": place.get("businessStatus"),
            "google_maps_uri": place.get("googleMapsUri"),
            "photo_names": photo_names,
            "opening_hours": [
                str(value) for value in regular_hours.get("weekdayDescriptions", [])
            ],
            "current_opening_hours": [
                str(value) for value in current_hours.get("weekdayDescriptions", [])
            ],
            "website_uri": place.get("websiteUri"),
            "national_phone_number": place.get("nationalPhoneNumber"),
            "editorial_summary": GoogleMapsService._text(place.get("editorialSummary")),
            "source": "Google Places API (New)",
        }

    async def search_destinations(
        self,
        query: str,
        *,
        limit: int = 10,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        result_limit = max(1, min(limit, 20))
        language_code = language or self._settings.google_maps_language
        cache_key = ("search", query.strip().casefold(), result_limit, language_code)

        async def fetch() -> list[dict[str, Any]]:
            body: dict[str, Any] = {
                "textQuery": query,
                "maxResultCount": result_limit,
                "languageCode": language_code,
            }
            payload = await self._request(
                "POST",
                f"{PLACES_BASE}/places:searchText",
                action="Places text search",
                headers=self._place_headers(",".join(PLACE_SUMMARY_FIELDS)),
                json=body,
            )
            places = payload.get("places") if isinstance(payload, dict) else None
            if not isinstance(places, list):
                return []
            return [
                self._normalise_place(place)
                for place in places
                if isinstance(place, dict)
            ]

        return await self._cache.get_or_set(cache_key, fetch)

    async def get_place_details(self, place_id: str) -> dict[str, Any]:
        cache_key = ("details", place_id, self._settings.google_maps_language)

        async def fetch() -> dict[str, Any]:
            encoded = quote(place_id, safe="")
            payload = await self._request(
                "GET",
                f"{PLACES_BASE}/places/{encoded}",
                action="Places details",
                headers=self._place_headers(",".join(PLACE_DETAIL_FIELDS)),
                params={"languageCode": self._settings.google_maps_language},
            )
            if not isinstance(payload, dict) or not payload.get("id"):
                raise ExternalServiceError(
                    "Google Places returned an invalid place payload."
                )
            return self._normalise_place(payload)

        return await self._cache.get_or_set(cache_key, fetch)

    async def nearby_places(
        self,
        *,
        latitude: float,
        longitude: float,
        included_types: list[str],
        limit: int = 15,
        radius_m: int = 10_000,
        category: ActivityCategory | None = None,
    ) -> list[dict[str, Any]]:
        result_limit = max(1, min(limit, 20))
        radius = max(500, min(radius_m, 50_000))
        cache_key = (
            "nearby",
            round(latitude, 5),
            round(longitude, 5),
            tuple(sorted(str(item) for item in included_types)),
            result_limit,
            radius,
            category.value if category else None,
        )

        async def fetch() -> list[dict[str, Any]]:
            body = {
                "includedTypes": included_types,
                "maxResultCount": result_limit,
                "rankPreference": "POPULARITY",
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": radius,
                    }
                },
                "languageCode": self._settings.google_maps_language,
            }
            payload = await self._request(
                "POST",
                f"{PLACES_BASE}/places:searchNearby",
                action="Places nearby search",
                headers=self._place_headers(",".join(PLACE_SUMMARY_FIELDS)),
                json=body,
            )
            places = payload.get("places") if isinstance(payload, dict) else None
            if not isinstance(places, list):
                return []
            return [
                self._normalise_place(place, category=category)
                for place in places
                if isinstance(place, dict)
                and place.get("businessStatus") != "CLOSED_PERMANENTLY"
            ]

        return await self._cache.get_or_set(cache_key, fetch)

    async def geocode(self, address: str) -> dict[str, Any]:
        cache_key = (
            "geocode",
            address.strip().casefold(),
            self._settings.google_maps_language,
        )

        async def fetch() -> dict[str, Any]:
            key = self._require_key()
            payload = await self._request(
                "GET",
                GEOCODE_URL,
                action="Geocoding",
                params={
                    "address": address,
                    "key": key,
                    "language": self._settings.google_maps_language,
                },
            )
            status = payload.get("status") if isinstance(payload, dict) else None
            if status == "ZERO_RESULTS":
                raise NotFoundError("The address could not be geocoded.")
            if status != "OK":
                raise ExternalServiceError(
                    "Google Geocoding could not resolve the address.",
                    details={"upstream_status": status},
                )
            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list) or not results:
                raise NotFoundError("The address could not be geocoded.")
            result = results[0]
            geometry = result.get("geometry", {}) if isinstance(result, dict) else {}
            location = geometry.get("location", {}) if isinstance(geometry, dict) else {}
            return {
                "name": address,
                "address": result.get("formatted_address"),
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
                "place_id": result.get("place_id"),
            }

        return await self._cache.get_or_set(cache_key, fetch)

    async def resolve_destination(
        self,
        destination: str,
        destination_place_id: str | None = None,
    ) -> dict[str, Any]:
        if destination_place_id:
            place = await self.get_place_details(destination_place_id)
        else:
            results = await self.search_destinations(destination, limit=5)
            if not results:
                raise NotFoundError(
                    f"No destination matched '{destination}' in Google Places."
                )
            place = await self.get_place_details(results[0]["place_id"])
        if place.get("latitude") is None or place.get("longitude") is None:
            raise ExternalServiceError(
                "Google Places did not return coordinates for the destination."
            )
        return place

    async def resolve_location(self, location: dict[str, Any]) -> dict[str, Any]:
        place_id = location.get("place_id")
        address = location.get("address")
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        name = location.get("name")
        if place_id:
            place = await self.get_place_details(str(place_id))
            if place.get("latitude") is None or place.get("longitude") is None:
                raise ExternalServiceError("The place has no usable coordinates.")
            return {
                "name": place["name"],
                "address": place.get("formatted_address"),
                "latitude": float(place["latitude"]),
                "longitude": float(place["longitude"]),
                "place_id": place["place_id"],
            }
        if address:
            resolved = await self.geocode(str(address))
            if resolved.get("latitude") is None or resolved.get("longitude") is None:
                raise ExternalServiceError("Geocoding returned incomplete coordinates.")
            resolved["name"] = name or resolved.get("name")
            return resolved
        if latitude is None or longitude is None:
            raise NotFoundError("Route location could not be resolved.")
        return {
            "name": name,
            "address": None,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "place_id": None,
        }

    @staticmethod
    def _parse_duration(value: Any) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.endswith("s"):
            try:
                return int(float(value[:-1]))
            except ValueError:
                return 0
        return 0

    async def compute_route(
        self,
        *,
        origin: dict[str, Any],
        destination: dict[str, Any],
        travel_mode: TravelMode,
        include_steps: bool = False,
    ) -> dict[str, Any]:
        # Cache by rounded coordinates. Transit departures are rounded to the
        # hour because the Routes API response changes with departure time.
        departure_bucket = (
            datetime.now(timezone.utc).strftime("%Y%m%d%H")
            if travel_mode == TravelMode.TRANSIT
            else None
        )
        cache_key = (
            "route",
            round(float(origin["latitude"]), 5),
            round(float(origin["longitude"]), 5),
            round(float(destination["latitude"]), 5),
            round(float(destination["longitude"]), 5),
            travel_mode.value,
            include_steps,
            departure_bucket,
        )

        async def fetch() -> dict[str, Any]:
            field_parts = [
                "routes.distanceMeters",
                "routes.duration",
                "routes.polyline.encodedPolyline",
            ]
            if include_steps:
                field_parts.extend(
                    [
                        "routes.legs.steps.navigationInstruction",
                        "routes.legs.steps.distanceMeters",
                        "routes.legs.steps.staticDuration",
                    ]
                )
            body: dict[str, Any] = {
                "origin": {
                    "location": {
                        "latLng": {
                            "latitude": origin["latitude"],
                            "longitude": origin["longitude"],
                        }
                    }
                },
                "destination": {
                    "location": {
                        "latLng": {
                            "latitude": destination["latitude"],
                            "longitude": destination["longitude"],
                        }
                    }
                },
                "travelMode": travel_mode.value,
                "computeAlternativeRoutes": False,
                "languageCode": self._settings.google_maps_language,
                "units": "METRIC",
            }
            if travel_mode == TravelMode.DRIVE:
                body["routingPreference"] = "TRAFFIC_AWARE"
            if travel_mode == TravelMode.TRANSIT:
                departure = datetime.now(timezone.utc) + timedelta(hours=1)
                body["departureTime"] = departure.strftime("%Y-%m-%dT%H:%M:%SZ")

            payload = await self._request(
                "POST",
                ROUTES_URL,
                action="Routes",
                headers={
                    "X-Goog-Api-Key": self._require_key(),
                    "X-Goog-FieldMask": ",".join(field_parts),
                    "Content-Type": "application/json",
                },
                json=body,
            )
            routes = payload.get("routes") if isinstance(payload, dict) else None
            if not isinstance(routes, list) or not routes:
                raise NotFoundError(
                    "No route was found between the requested locations."
                )
            route = routes[0]
            duration_seconds = self._parse_duration(route.get("duration"))
            distance_meters = int(route.get("distanceMeters") or 0)
            polyline = None
            if isinstance(route.get("polyline"), dict):
                polyline = route["polyline"].get("encodedPolyline")

            steps: list[dict[str, Any]] = []
            if include_steps:
                legs = route.get("legs") if isinstance(route.get("legs"), list) else []
                for leg in legs:
                    raw_steps = leg.get("steps") if isinstance(leg, dict) else None
                    if not isinstance(raw_steps, list):
                        continue
                    for step in raw_steps:
                        if not isinstance(step, dict):
                            continue
                        instruction = step.get("navigationInstruction")
                        steps.append(
                            {
                                "instruction": (
                                    instruction.get("instructions")
                                    if isinstance(instruction, dict)
                                    else None
                                ),
                                "distance_meters": step.get("distanceMeters"),
                                "duration_seconds": self._parse_duration(
                                    step.get("staticDuration")
                                ),
                            }
                        )
            return {
                "origin": origin,
                "destination": destination,
                "travel_mode": travel_mode.value,
                "distance_meters": distance_meters,
                "distance_km": round(distance_meters / 1000, 2),
                "duration_seconds": duration_seconds,
                "duration_minutes": round(duration_seconds / 60, 1),
                "polyline": polyline,
                "steps": steps,
                "calculated_at": datetime.now(timezone.utc).isoformat(),
            }

        return await self._route_cache.get_or_set(cache_key, fetch)

    async def fetch_photo(self, photo_name: str, *, max_width: int = 1200) -> tuple[bytes, str]:
        if not PHOTO_NAME_PATTERN.fullmatch(photo_name):
            raise NotFoundError("Invalid Google Places photo name.")
        width = max(1, min(max_width, 1600))
        cache_key = ("photo", photo_name, width)

        async def fetch() -> tuple[bytes, str]:
            key = self._require_key()
            url = f"{PLACES_BASE}/{photo_name}/media"
            try:
                response = await self._client.get(
                    url,
                    params={"maxWidthPx": width, "key": key},
                    timeout=self._settings.google_maps_timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                raise ExternalServiceTimeoutError(
                    "Google Places photo timed out."
                ) from exc
            except httpx.HTTPError as exc:
                raise ExternalServiceError(
                    "Google Places photo is unreachable."
                ) from exc
            if response.status_code >= 400:
                raise ExternalServiceError(
                    "Google Places photo could not be retrieved.",
                    details={"upstream_status": response.status_code},
                )
            content_type = response.headers.get(
                "content-type", "image/jpeg"
            ).split(";")[0]
            if not content_type.startswith("image/"):
                raise ExternalServiceError(
                    "Google Places returned a non-image photo response."
                )
            return response.content, content_type

        return await self._photo_cache.get_or_set(cache_key, fetch)
