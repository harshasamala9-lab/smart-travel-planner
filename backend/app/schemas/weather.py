"""Weather API response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.models.enums import WeatherUnits
from app.schemas.common import ResponseModel


class WeatherCondition(ResponseModel):
    main: str
    description: str
    icon: str | None = None


class CurrentWeather(ResponseModel):
    observed_at: datetime
    temperature: float
    feels_like: float
    temp_min: float
    temp_max: float
    humidity: int
    pressure: int
    wind_speed: float
    wind_degrees: int | None = None
    condition: WeatherCondition
    sunrise: datetime | None = None
    sunset: datetime | None = None
    units: WeatherUnits


class ForecastDay(ResponseModel):
    date: date
    temp_min: float
    temp_max: float
    average_temperature: float
    humidity: int
    precipitation_probability: float | None = None
    condition: WeatherCondition
    summary: str


class WeatherResponse(ResponseModel):
    destination: str
    country: str | None = None
    latitude: float
    longitude: float
    units: WeatherUnits
    current: CurrentWeather
    forecast: list[ForecastDay] = Field(default_factory=list)
    requested_start_date: date | None = None
    requested_end_date: date | None = None
    forecast_covers_requested_dates: bool | None = None
    suggestions: list[str] = Field(default_factory=list)
    source: str = "OpenWeather API"
    disclaimer: str = (
        "Current conditions are the latest observation returned by OpenWeather. "
        "Forecast data covers the provider's available forecast horizon only."
    )
    fetched_at: datetime
    attribution: str = "Weather data by OpenWeather"
