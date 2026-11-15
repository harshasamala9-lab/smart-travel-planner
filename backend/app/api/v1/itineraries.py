"""Itinerary generation, listing, retrieval, update, and deletion."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.dependencies import (
    CurrentUser,
    SettingsDep,
    get_export_service,
    get_itinerary_service,
    get_share_service,
)
from app.schemas.itineraries import (
    GenerateItineraryRequest,
    ItineraryDetailResponse,
    ItineraryListResponse,
    ItineraryUpdateRequest,
)
from app.schemas.shares import (
    ShareCreateRequest,
    ShareListResponse,
    ShareResponse,
)
from app.services.export_service import ExportService
from app.services.itinerary_service import ItineraryService
from app.services.share_service import ShareService

router = APIRouter(prefix="/itineraries", tags=["Itineraries"])


@router.post(
    "/generate",
    response_model=ItineraryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and save a personalised itinerary",
    description=(
        "Resolves the destination with Google Places, gathers real candidate places and "
        "weather, asks Gemini for a structured plan, validates every place ID and date, "
        "enriches travel legs with Google Routes, calculates an estimated budget, and saves "
        "the itinerary under the authenticated user. This endpoint is available only when "
        "GOOGLE_MAPS_API_KEY and GEMINI_API_KEY are configured."
    ),
    responses={
        422: {"description": "Invalid preferences or no viable candidates"},
        502: {"description": "Gemini or Google Maps returned an unusable response"},
        503: {"description": "Gemini or Google Maps is not configured"},
    },
)
async def generate_itinerary(
    payload: GenerateItineraryRequest,
    user: CurrentUser,
    service: Annotated[ItineraryService, Depends(get_itinerary_service)],
) -> ItineraryDetailResponse:
    itinerary = await service.generate_itinerary(user, payload)
    return ItineraryDetailResponse(**itinerary)


@router.get(
    "",
    response_model=ItineraryListResponse,
    summary="List the authenticated user's itineraries",
)
async def list_itineraries(
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
    "/{itinerary_id}",
    response_model=ItineraryDetailResponse,
    summary="Get one of the authenticated user's itineraries",
    responses={404: {"description": "Itinerary not found or not owned by this user"}},
)
async def get_itinerary(
    itinerary_id: UUID,
    user: CurrentUser,
    service: Annotated[ItineraryService, Depends(get_itinerary_service)],
) -> ItineraryDetailResponse:
    itinerary = await service.get_itinerary(user.user_id, itinerary_id)
    return ItineraryDetailResponse(**itinerary)


@router.patch(
    "/{itinerary_id}",
    response_model=ItineraryDetailResponse,
    summary="Update itinerary metadata or replace its days/activities",
    description=(
        "Only the owner can update an itinerary. If `days` is supplied, it replaces all "
        "existing days and activities, and the budget estimate is recalculated. User edits "
        "are treated as estimates, never verified live prices."
    ),
    responses={404: {"description": "Itinerary not found"}},
)
async def update_itinerary(
    itinerary_id: UUID,
    payload: ItineraryUpdateRequest,
    user: CurrentUser,
    service: Annotated[ItineraryService, Depends(get_itinerary_service)],
) -> ItineraryDetailResponse:
    itinerary = await service.update_itinerary(user.user_id, itinerary_id, payload)
    return ItineraryDetailResponse(**itinerary)


@router.delete(
    "/{itinerary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's itineraries",
    responses={404: {"description": "Itinerary not found"}},
)
async def delete_itinerary(
    itinerary_id: UUID,
    user: CurrentUser,
    service: Annotated[ItineraryService, Depends(get_itinerary_service)],
) -> Response:
    await service.delete_itinerary(user.user_id, itinerary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{itinerary_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a read-only share link for an itinerary",
    description=(
        "The link token is returned once. Only its SHA-256 hash is stored. Links "
        "expire automatically and can be revoked by the owner. Shared views exclude "
        "account and preference data."
    ),
    responses={404: {"description": "Itinerary not found"}},
)
async def create_share_link(
    itinerary_id: UUID,
    payload: ShareCreateRequest,
    request: Request,
    user: CurrentUser,
    settings: SettingsDep,
    service: Annotated[ShareService, Depends(get_share_service)],
) -> ShareResponse:
    share = await service.create(
        user.user_id,
        itinerary_id,
        expires_in_days=payload.expires_in_days,
    )
    api_path = (
        f"{settings.api_v1_prefix}/shared/itineraries/{share['token']}"
    )
    share_url = f"{str(request.base_url).rstrip('/')}{api_path}"
    return ShareResponse(**share, share_url=share_url, api_path=api_path)


@router.get(
    "/{itinerary_id}/shares",
    response_model=ShareListResponse,
    summary="List active share links for an itinerary",
    description="Share tokens are never returned by this endpoint.",
    responses={404: {"description": "Itinerary not found"}},
)
async def list_share_links(
    itinerary_id: UUID,
    user: CurrentUser,
    service: Annotated[ShareService, Depends(get_share_service)],
) -> ShareListResponse:
    return ShareListResponse(
        **await service.list_for_itinerary(user.user_id, itinerary_id)
    )


@router.delete(
    "/{itinerary_id}/shares",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke every active share link for an itinerary",
    responses={404: {"description": "Itinerary not found"}},
)
async def revoke_share_links(
    itinerary_id: UUID,
    user: CurrentUser,
    service: Annotated[ShareService, Depends(get_share_service)],
) -> Response:
    await service.revoke_all(user.user_id, itinerary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{itinerary_id}/export/pdf",
    summary="Download an itinerary as a PDF",
    description=(
        "Generates a printable PDF with the itinerary, activities, budget estimate, "
        "and all data-honesty disclaimers."
    ),
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Itinerary not found"},
    },
)
async def export_itinerary_pdf(
    itinerary_id: UUID,
    user: CurrentUser,
    itinerary_service: Annotated[
        ItineraryService, Depends(get_itinerary_service)
    ],
    export_service: Annotated[ExportService, Depends(get_export_service)],
) -> Response:
    itinerary = await itinerary_service.get_itinerary(user.user_id, itinerary_id)
    pdf = export_service.build_itinerary_pdf(itinerary)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="smart-travel-{itinerary_id}.pdf"'
            ),
            "Content-Length": str(len(pdf)),
        },
    )
