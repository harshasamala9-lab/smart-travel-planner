"""User travel analytics and downloadable CSV reports."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import (
    CurrentUser,
    get_analytics_service,
    get_itinerary_service,
)
from app.schemas.analytics import TravelAnalyticsResponse
from app.services.analytics_service import AnalyticsService
from app.services.itinerary_service import ItineraryService

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Spreadsheet applications may interpret cells beginning with these characters
# as formulas. Prefixing them with an apostrophe keeps user/AI-supplied text
# inert while preserving the displayed value.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: object) -> object:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


@router.get(
    "/me",
    response_model=TravelAnalyticsResponse,
    summary="Get currency-safe travel analytics for the authenticated user",
    description=(
        "Currencies are kept separate. Budgets and activity costs are planning "
        "estimates and are never represented as verified live prices."
    ),
)
async def my_analytics(
    user: CurrentUser,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> TravelAnalyticsResponse:
    return TravelAnalyticsResponse(**await service.build(user.user_id))


@router.get(
    "/me/export.csv",
    summary="Download a CSV report of the authenticated user's itineraries",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_csv(
    user: CurrentUser,
    service: Annotated[ItineraryService, Depends(get_itinerary_service)],
) -> Response:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "title",
            "destination_name",
            "start_date",
            "end_date",
            "travellers",
            "status",
            "currency",
            "total_budget",
            "estimated_total",
            "created_at",
        ],
    )
    writer.writeheader()
    offset = 0
    page_size = 100
    while True:
        result = await service.list_itineraries(
            user.user_id, limit=page_size, offset=offset
        )
        for item in result["items"]:
            estimate = item.get("budget_estimate") or {}
            row = {
                "id": item["id"],
                "title": item["title"],
                "destination_name": item["destination_name"],
                "start_date": item["start_date"],
                "end_date": item["end_date"],
                "travellers": item["travellers"],
                "status": item["status"],
                "currency": item["currency"],
                "total_budget": item["total_budget"],
                "estimated_total": estimate.get("total", ""),
                "created_at": item["created_at"],
            }
            writer.writerow({key: _csv_safe(value) for key, value in row.items()})
        if len(result["items"]) < page_size:
            break
        offset += page_size
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="smart-travel-report-{date.today().isoformat()}.csv"'
            )
        },
    )
