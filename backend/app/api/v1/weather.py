"""OpenWeather endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.exceptions import ValidationAppError
from app.dependencies import CurrentUser, get_weather_service
from app.models.enums import WeatherUnits
from app.schemas.weather import WeatherResponse
from app.services.weather_service import OpenWeatherService

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get(
    "/{destination}",
    response_model=WeatherResponse,
    summary="Current observed weather and available forecast for a destination",
    description=(
        "Uses OpenWeather's latest observation and its available 5-day/3-hour forecast. "
        "The response explicitly states whether the forecast covers the requested dates. "
        "It does not claim availability of real-time weather beyond the provider's data."
    ),
    responses={
        404: {"description": "Destination not found by OpenWeather geocoding"},
        503: {"description": "OpenWeather is not configured"},
    },
)
async def get_weather(
    destination: str,
    _user: CurrentUser,
    weather: Annotated[OpenWeatherService, Depends(get_weather_service)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    units: Annotated[WeatherUnits, Query()] = WeatherUnits.METRIC,
) -> WeatherResponse:
    if (start_date is None) != (end_date is None):
        raise ValidationAppError("Provide both start_date and end_date, or neither.")
    if start_date and end_date and end_date < start_date:
        raise ValidationAppError("end_date must be on or after start_date.")
    result = await weather.get_weather(
        destination,
        start_date=start_date,
        end_date=end_date,
        units=units,
    )
    return WeatherResponse(**result)
