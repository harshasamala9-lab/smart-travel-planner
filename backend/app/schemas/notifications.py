"""In-app notification schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import ResponseModel

NotificationType = Literal[
    "trip_generated",
    "trip_reminder",
    "system",
    "offer",
    "review",
    "share",
]


class NotificationResponse(ResponseModel):
    id: UUID
    type: NotificationType
    title: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime


class NotificationListResponse(ResponseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    limit: int
    offset: int


class MarkAllReadResponse(ResponseModel):
    marked: int
    unread_count: int = 0
