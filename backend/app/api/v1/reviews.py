"""Review creation, browsing, editing, and deletion."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencies import CurrentUser, get_review_service
from app.schemas.reviews import (
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpdate,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get(
    "/me",
    response_model=ReviewListResponse,
    summary="List the authenticated user's reviews",
)
async def my_reviews(
    user: CurrentUser,
    service: Annotated[ReviewService, Depends(get_review_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewListResponse:
    return ReviewListResponse(
        **await service.list_for_user(user.user_id, limit=limit, offset=offset)
    )


@router.get(
    "/place/{place_id}",
    response_model=ReviewListResponse,
    summary="List user reviews for a Google Places place",
    description=(
        "These are user-submitted reviews, not Google ratings, and are not "
        "verified visit records."
    ),
)
async def place_reviews(
    place_id: str,
    user: CurrentUser,
    service: Annotated[ReviewService, Depends(get_review_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewListResponse:
    return ReviewListResponse(
        **await service.list_for_place(
            user.user_id, place_id, limit=limit, offset=offset
        )
    )


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review for a verified Google Places place",
    responses={
        404: {"description": "Place not found in Google Places"},
        409: {"description": "The user already reviewed this place"},
        503: {"description": "Google Places is not configured"},
    },
)
async def create_review(
    payload: ReviewCreate,
    user: CurrentUser,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    return ReviewResponse(**await service.create(user.user_id, payload))


@router.patch(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Update one of the authenticated user's reviews",
    responses={404: {"description": "Review not found or not owned by this user"}},
)
async def update_review(
    review_id: UUID,
    payload: ReviewUpdate,
    user: CurrentUser,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    return ReviewResponse(
        **await service.update(user.user_id, review_id, payload)
    )


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's reviews",
    responses={404: {"description": "Review not found or not owned by this user"}},
)
async def delete_review(
    review_id: UUID,
    user: CurrentUser,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> Response:
    await service.delete(user.user_id, review_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
