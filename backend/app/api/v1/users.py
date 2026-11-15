"""User profile, travel preference, history, and saved-destination endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.exceptions import NotFoundError
from app.dependencies import (
    CurrentUser,
    get_itinerary_service,
    get_maps_service,
    get_profile_repository,
)
from app.database.repositories import ProfileRepository
from app.schemas.common import MessageResponse
from app.schemas.itineraries import ItineraryListResponse
from app.schemas.users import (
    ProfileResponse,
    ProfileUpdateRequest,
    SavedDestinationCreate,
    SavedDestinationList,
    SavedDestinationResponse,
    TravelPreferencesInput,
    TravelPreferencesResponse,
)
from app.services.itinerary_service import ItineraryService
from app.services.maps_service import GoogleMapsService
from app.services.travel_search_service import get_travel_search

router = APIRouter(prefix="/users", tags=["Users"])


async def _ensure_profile(
    profiles: ProfileRepository,
    user: CurrentUser,
) -> dict:
    profile = await profiles.get_by_id(user.user_id)
    if profile is not None:
        return profile
    return await profiles.ensure_from_auth(
        user_id=user.user_id,
        email=user.email or f"{user.user_id}@no-email.invalid",
        full_name=user.full_name,
        avatar_url=user.avatar_url,
    )


@router.get(
    "/me",
    response_model=ProfileResponse,
    summary="Get the authenticated user's profile",
)
async def get_me(
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileResponse:
    profile = await _ensure_profile(profiles, user)
    return ProfileResponse(**profile)


@router.patch(
    "/me",
    response_model=ProfileResponse,
    summary="Update the authenticated user's profile",
    description="Email and passwords are managed by Neon Auth and cannot be edited here.",
)
async def update_me(
    payload: ProfileUpdateRequest,
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> ProfileResponse:
    await _ensure_profile(profiles, user)
    values = payload.model_dump(exclude_unset=True)
    profile = await profiles.update(user.user_id, values)
    if profile is None:
        raise NotFoundError("Profile not found.")
    return ProfileResponse(**profile)


@router.get(
    "/me/preferences",
    response_model=TravelPreferencesResponse,
    summary="Get saved travel preferences",
    responses={404: {"description": "No preferences saved yet"}},
)
async def get_preferences(
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> TravelPreferencesResponse:
    preferences = await profiles.get_preferences(user.user_id)
    if preferences is None:
        raise NotFoundError("No travel preferences have been saved yet.")
    return TravelPreferencesResponse(**preferences)


@router.put(
    "/me/preferences",
    response_model=TravelPreferencesResponse,
    summary="Create or replace travel preferences",
)
async def put_preferences(
    payload: TravelPreferencesInput,
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> TravelPreferencesResponse:
    await _ensure_profile(profiles, user)
    preferences = await profiles.upsert_preferences(
        user.user_id, payload.model_dump(mode="json")
    )
    return TravelPreferencesResponse(**preferences)


@router.get(
    "/me/history",
    response_model=ItineraryListResponse,
    summary="Retrieve saved travel history (itineraries)",
)
async def get_history(
    user: CurrentUser,
    service: Annotated[ItineraryService, Depends(get_itinerary_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ItineraryListResponse:
    result = await service.list_itineraries(
        user.user_id, limit=limit, offset=offset
    )
    return ItineraryListResponse(**result)


@router.get(
    "/me/saved-destinations",
    response_model=SavedDestinationList,
    summary="List saved destinations",
)
async def list_saved_destinations(
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> SavedDestinationList:
    items = await profiles.list_saved_destinations(user.user_id)
    return SavedDestinationList(
        items=[SavedDestinationResponse(**item) for item in items],
        total=len(items),
    )


@router.post(
    "/me/saved-destinations",
    response_model=SavedDestinationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a Google Places destination",
    description=(
        "The place is resolved through Google Places before storage, so arbitrary or "
        "invented place IDs are rejected."
    ),
)
async def save_destination(
    payload: SavedDestinationCreate,
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
    maps: Annotated[GoogleMapsService, Depends(get_maps_service)],
) -> SavedDestinationResponse:
    await _ensure_profile(profiles, user)
    curated = get_travel_search().get(payload.place_id)
    if curated is not None:
        place = {
            "place_id": curated["id"],
            "name": curated["name"],
            "formatted_address": curated.get("address"),
            "latitude": curated.get("latitude"),
            "longitude": curated.get("longitude"),
            "types": [curated.get("travel_type") or "travel_destination"],
        }
    else:
        place = await maps.get_place_details(payload.place_id)
    category = place.get("types", ["place"])[0] if place.get("types") else "place"
    saved = await profiles.add_saved_destination(
        user.user_id,
        {
            "place_id": place["place_id"],
            "name": place["name"],
            "address": place.get("formatted_address"),
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "category": category,
            "notes": payload.notes,
        },
    )
    return SavedDestinationResponse(**saved)


@router.delete(
    "/me/saved-destinations/{place_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a saved destination",
    responses={404: {"description": "Saved destination not found"}},
)
async def delete_saved_destination(
    place_id: str,
    user: CurrentUser,
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> Response:
    deleted = await profiles.delete_saved_destination(user.user_id, place_id)
    if not deleted:
        raise NotFoundError("Saved destination not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
