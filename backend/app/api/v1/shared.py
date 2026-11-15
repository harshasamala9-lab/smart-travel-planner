"""Public, token-protected read-only itinerary sharing."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_share_service
from app.schemas.shares import SharedItineraryResponse
from app.services.share_service import ShareService

router = APIRouter(prefix="/shared", tags=["Sharing"])


@router.get(
    "/itineraries/{token}",
    response_model=SharedItineraryResponse,
    summary="View a shared itinerary using its secret token",
    description=(
        "No authentication is required. The token is high-entropy, stored only "
        "as a SHA-256 hash, and can expire or be revoked by the owner."
    ),
    responses={404: {"description": "Share link is invalid, expired, or revoked"}},
)
async def shared_itinerary(
    token: str,
    service: Annotated[ShareService, Depends(get_share_service)],
) -> SharedItineraryResponse:
    return SharedItineraryResponse(**await service.resolve(token))
