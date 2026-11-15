"""Destination discovery, place details, photo proxy, and route planning."""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.exceptions import (
    ExternalServiceError,
    NotFoundError,
    ValidationAppError,
)
from app.dependencies import CurrentUser, get_maps_service
from app.models.enums import ActivityCategory
from app.schemas.destinations import (
    DestinationSearchResponse,
    NearbyPlacesResponse,
    PlaceDetails,
    PlaceSummary,
    RouteRequest,
    RouteResponse,
)
from app.services.maps_service import GoogleMapsService
from app.services.travel_search_service import (
    CATALOG_SOURCE,
    GOOGLE_SOURCE,
    get_travel_search,
)
from app.utils.interests import (
    ALLOWED_NEARBY_TYPES,
    DEFAULT_ATTRACTION_TYPES,
    RESTAURANT_TYPES,
)

router = APIRouter(prefix="/destinations", tags=["Destinations"])
logger = logging.getLogger(__name__)


async def _details(maps: GoogleMapsService, place_id: str) -> dict:
    return await maps.get_place_details(place_id)


async def _resolve_place(maps: GoogleMapsService, place_id: str) -> dict:
    """Resolve curated catalog IDs locally and Google IDs through the API."""
    curated = get_travel_search().get(place_id)
    if curated is not None:
        return get_travel_search().to_place(curated)
    return await _details(maps, place_id)


def _curated_nearby_fallback(
    place_id: str,
    place: dict,
    *,
    radius_m: int,
    included_types: list[str],
    message: str,
) -> NearbyPlacesResponse:
    return NearbyPlacesResponse(
        place_id=place_id,
        destination_name=place["name"],
        items=[],
        count=0,
        radius_m=radius_m,
        included_types=included_types,
        source=CATALOG_SOURCE,
        message=message,
    )


@router.get(
    "/search",
    response_model=DestinationSearchResponse,
    summary="Travel-only destination search",
    description=(
        "Searches curated travel destinations and, when configured, Google "
        "Places. Results are filtered to travel categories only; unrelated "
        "local businesses, shops and services are never returned. The curated "
        "catalog keeps search working when Google Maps is not configured."
    ),
    responses={503: {"description": "Google Maps is not configured"}},
)
async def search_destinations(
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
    query: Annotated[str, Query(min_length=2, max_length=200, alias="query")],
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
    language: Annotated[str | None, Query(min_length=2, max_length=10)] = None,
    category: Annotated[
        str | None,
        Query(description="Travel filter: city, beach, nature, historical, food, stay"),
    ] = None,
) -> DestinationSearchResponse:
    search = get_travel_search()
    outcome = search.search(query, limit=limit, category=category)

    google_items: list[dict] = []
    google_failed = False
    if maps.is_configured and not outcome.blocked:
        try:
            raw = await maps.search_destinations(
                query, limit=min(20, max(limit * 2, 10)), language=language
            )
            google_items = search.filter_google(raw)
        except ExternalServiceError as exc:
            google_failed = True
            logger.warning(
                "Google Places search unavailable, using curated catalog: %s",
                exc.message,
            )

    # Curated matches first (they include a photo and a working guide page),
    # then live Google Places results that are not duplicates.
    items: list[dict] = [*outcome.items]
    seen = {str(item.get("name", "")).strip().lower() for item in items}
    for item in google_items:
        key = str(item.get("name", "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            items.append(item)
    items = items[:limit]

    if outcome.items and google_items:
        source = f"{CATALOG_SOURCE} + {GOOGLE_SOURCE}"
    elif google_items:
        source = GOOGLE_SOURCE
    else:
        source = CATALOG_SOURCE

    message = outcome.message if not items else None
    if google_failed and items:
        message = (
            "Live Google results are temporarily unavailable; showing curated "
            "travel guides."
        )

    return DestinationSearchResponse(
        query=query,
        items=[PlaceSummary(**item) for item in items],
        count=len(items),
        source=source,
        suggestions=outcome.suggestions if not items else [],
        message=message,
    )


@router.get(
    "/featured",
    response_model=DestinationSearchResponse,
    summary="Curated featured travel destinations",
    description=(
        "Editor-picked destinations from the built-in travel catalog with "
        "verified free-license photography. Public read-only data."
    ),
)
async def featured_destinations(
    limit: Annotated[int, Query(ge=1, le=40)] = 12,
    category: Annotated[str | None, Query(max_length=30)] = None,
) -> DestinationSearchResponse:
    items = get_travel_search().featured(limit=limit, category=category)
    return DestinationSearchResponse(
        query="featured",
        items=[PlaceSummary(**item) for item in items],
        count=len(items),
        source=CATALOG_SOURCE,
    )


@router.get(
    "/photo",
    summary="Proxy a Google Places photo without exposing the API key",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}}},
        404: {"description": "Invalid photo name"},
    },
)
async def destination_photo(
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
    photo_name: Annotated[str, Query(min_length=10, max_length=500)],
    max_width: Annotated[int, Query(ge=100, le=1600)] = 1200,
) -> Response:
    content, content_type = await maps.fetch_photo(photo_name, max_width=max_width)
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Calculate a route with Google Routes API",
    description=(
        "Provide exactly one location form per endpoint: place_id, address, or "
        "latitude/longitude. Distance and duration come from Google Routes."
    ),
    responses={503: {"description": "Google Maps is not configured"}},
)
async def compute_route(
    payload: RouteRequest,
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
) -> RouteResponse:
    origin = await maps.resolve_location(payload.origin.model_dump())
    destination = await maps.resolve_location(payload.destination.model_dump())
    result = await maps.compute_route(
        origin=origin,
        destination=destination,
        travel_mode=payload.travel_mode,
        include_steps=payload.include_steps,
    )
    return RouteResponse(**result)


@router.get(
    "/{place_id}",
    response_model=PlaceDetails,
    summary="Get destination details",
    description=(
        "Returns a curated travel guide for catalog IDs (prefixed "
        "``curated-``) or Google Places details when configured."
    ),
)
async def get_destination(
    place_id: str,
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
) -> PlaceDetails:
    curated = get_travel_search().get(place_id)
    if curated is not None:
        latitude = curated.get("latitude")
        longitude = curated.get("longitude")
        payload = get_travel_search().to_place(curated)
        payload["google_maps_uri"] = (
            f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
            if latitude is not None and longitude is not None
            else None
        )
        payload["website_uri"] = (
            "https://en.wikipedia.org/wiki/"
            + quote(str(curated.get("wiki_title", curated["name"])).replace(" ", "_"))
        )
        payload["editorial_summary"] = curated.get("description")
        payload["current_opening_hours"] = []
        return PlaceDetails(**payload)
    place = await _details(maps, place_id)
    return PlaceDetails(**place)


@router.get(
    "/{place_id}/attractions",
    response_model=NearbyPlacesResponse,
    summary="Discover tourist attractions near a destination",
)
async def nearby_attractions(
    place_id: str,
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
    radius_m: Annotated[int, Query(ge=500, le=50_000)] = 10_000,
    limit: Annotated[int, Query(ge=1, le=20)] = 15,
) -> NearbyPlacesResponse:
    place = await _resolve_place(maps, place_id)
    if place.get("latitude") is None or place.get("longitude") is None:
        raise ExternalServiceError("This place has no coordinates for a nearby search.")
    curated = get_travel_search().get(place_id)
    if curated is not None and not maps.is_configured:
        return _curated_nearby_fallback(
            place_id,
            place,
            radius_m=radius_m,
            included_types=DEFAULT_ATTRACTION_TYPES,
            message=(
                "Live nearby attractions need a Google Maps key. The curated "
                "travel guide above still works without one."
            ),
        )
    try:
        items = await maps.nearby_places(
            latitude=float(place["latitude"]),
            longitude=float(place["longitude"]),
            included_types=DEFAULT_ATTRACTION_TYPES,
            limit=limit,
            radius_m=radius_m,
            category=ActivityCategory.ATTRACTION,
        )
    except ExternalServiceError:
        if curated is None:
            raise
        return _curated_nearby_fallback(
            place_id,
            place,
            radius_m=radius_m,
            included_types=DEFAULT_ATTRACTION_TYPES,
            message="Live nearby attractions are temporarily unavailable.",
        )
    return NearbyPlacesResponse(
        place_id=place_id,
        destination_name=place["name"],
        items=[PlaceSummary(**item) for item in items],
        count=len(items),
        radius_m=radius_m,
        included_types=DEFAULT_ATTRACTION_TYPES,
        source=CATALOG_SOURCE if curated is not None else GOOGLE_SOURCE,
    )


@router.get(
    "/{place_id}/restaurants",
    response_model=NearbyPlacesResponse,
    summary="Find restaurants near a destination",
)
async def nearby_restaurants(
    place_id: str,
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
    radius_m: Annotated[int, Query(ge=500, le=50_000)] = 5_000,
    limit: Annotated[int, Query(ge=1, le=20)] = 15,
) -> NearbyPlacesResponse:
    place = await _resolve_place(maps, place_id)
    if place.get("latitude") is None or place.get("longitude") is None:
        raise ExternalServiceError("This place has no coordinates for a nearby search.")
    curated = get_travel_search().get(place_id)
    if curated is not None and not maps.is_configured:
        return _curated_nearby_fallback(
            place_id,
            place,
            radius_m=radius_m,
            included_types=RESTAURANT_TYPES,
            message=(
                "Live nearby restaurants need a Google Maps key. The curated "
                "travel guide above still works without one."
            ),
        )
    try:
        items = await maps.nearby_places(
            latitude=float(place["latitude"]),
            longitude=float(place["longitude"]),
            included_types=RESTAURANT_TYPES,
            limit=limit,
            radius_m=radius_m,
            category=ActivityCategory.RESTAURANT,
        )
    except ExternalServiceError:
        if curated is None:
            raise
        return _curated_nearby_fallback(
            place_id,
            place,
            radius_m=radius_m,
            included_types=RESTAURANT_TYPES,
            message="Live nearby restaurants are temporarily unavailable.",
        )
    return NearbyPlacesResponse(
        place_id=place_id,
        destination_name=place["name"],
        items=[PlaceSummary(**item) for item in items],
        count=len(items),
        radius_m=radius_m,
        included_types=RESTAURANT_TYPES,
        source=CATALOG_SOURCE if curated is not None else GOOGLE_SOURCE,
    )


@router.get(
    "/{place_id}/nearby",
    response_model=NearbyPlacesResponse,
    summary="Find nearby places for selected Google place types",
    description=(
        "Example: /destinations/{place_id}/nearby?types=tourist_attraction,museum. "
        "Only Google Places types supported by this API are accepted."
    ),
)
async def nearby_places(
    place_id: str,
    _user: CurrentUser,
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
    types: Annotated[
        str | None,
        Query(description="Comma-separated Google Places types"),
    ] = None,
    radius_m: Annotated[int, Query(ge=500, le=50_000)] = 10_000,
    limit: Annotated[int, Query(ge=1, le=20)] = 15,
) -> NearbyPlacesResponse:
    place = await _resolve_place(maps, place_id)
    if place.get("latitude") is None or place.get("longitude") is None:
        raise ExternalServiceError("This place has no coordinates for a nearby search.")
    requested = (
        [item.strip() for item in types.split(",") if item.strip()]
        if types
        else ["tourist_attraction"]
    )
    invalid = [item for item in requested if item not in ALLOWED_NEARBY_TYPES]
    if invalid:
        raise ValidationAppError(
            "Unsupported Google place type(s).",
            details={
                "invalid_types": invalid,
                "allowed_types": sorted(ALLOWED_NEARBY_TYPES),
            },
        )
    requested = list(dict.fromkeys(requested))
    curated = get_travel_search().get(place_id)
    if curated is not None and not maps.is_configured:
        return _curated_nearby_fallback(
            place_id,
            place,
            radius_m=radius_m,
            included_types=requested,
            message=(
                "Live nearby search needs a Google Maps key. The curated "
                "travel guide above still works without one."
            ),
        )
    try:
        items = await maps.nearby_places(
            latitude=float(place["latitude"]),
            longitude=float(place["longitude"]),
            included_types=requested,
            limit=limit,
            radius_m=radius_m,
        )
    except ExternalServiceError:
        if curated is None:
            raise
        return _curated_nearby_fallback(
            place_id,
            place,
            radius_m=radius_m,
            included_types=requested,
            message="Live nearby search is temporarily unavailable.",
        )
    for item in items:
        place_types = set(item.get("types") or [])
        if place_types.intersection(RESTAURANT_TYPES):
            item["category"] = ActivityCategory.RESTAURANT.value
        elif "lodging" in place_types:
            item["category"] = ActivityCategory.HOTEL.value
        elif item.get("category") is None:
            item["category"] = ActivityCategory.ATTRACTION.value
    return NearbyPlacesResponse(
        place_id=place_id,
        destination_name=place["name"],
        items=[PlaceSummary(**item) for item in items],
        count=len(items),
        radius_m=radius_m,
        included_types=requested,
        source=CATALOG_SOURCE if curated is not None else GOOGLE_SOURCE,
    )
