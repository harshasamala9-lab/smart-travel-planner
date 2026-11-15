"""In-app notification endpoints.

Real-time delivery can use Neon Realtime subscriptions on the
``notifications`` table (RLS-scoped to the authenticated user). The REST
endpoints below are the source of truth and support polling clients.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.exceptions import NotFoundError
from app.dependencies import CurrentUser, get_notification_repository
from app.database.repositories import NotificationRepository
from app.schemas.notifications import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _body(row: dict) -> dict:
    return {**row, "read": row.get("read_at") is not None}


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List the authenticated user's notifications",
)
async def list_notifications(
    user: CurrentUser,
    repository: Annotated[
        NotificationRepository, Depends(get_notification_repository)
    ],
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    items, total, unread = await repository.list_for_user(
        user.user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        items=[NotificationResponse(**_body(item)) for item in items],
        total=total,
        unread_count=unread,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    user: CurrentUser,
    repository: Annotated[
        NotificationRepository, Depends(get_notification_repository)
    ],
) -> MarkAllReadResponse:
    marked = await repository.mark_all_read(user.user_id)
    return MarkAllReadResponse(marked=marked, unread_count=0)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark one notification as read",
    responses={404: {"description": "Notification not found"}},
)
async def mark_read(
    notification_id: UUID,
    user: CurrentUser,
    repository: Annotated[
        NotificationRepository, Depends(get_notification_repository)
    ],
) -> NotificationResponse:
    row = await repository.mark_read(user.user_id, notification_id)
    if row is None:
        raise NotFoundError("Notification not found.")
    return NotificationResponse(**_body(row))


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's notifications",
    responses={404: {"description": "Notification not found"}},
)
async def delete_notification(
    notification_id: UUID,
    user: CurrentUser,
    repository: Annotated[
        NotificationRepository, Depends(get_notification_repository)
    ],
) -> Response:
    deleted = await repository.delete(user.user_id, notification_id)
    if not deleted:
        raise NotFoundError("Notification not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
