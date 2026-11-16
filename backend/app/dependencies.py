"""FastAPI dependency providers.

All services are created once in the application lifespan and shared through
``app.state``. Tests override these callables with fakes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import AuthenticatedUser, NeonTokenVerifier
from app.database.connection import Database
from app.database.repositories import (
    AnalyticsRepository,
    ItineraryRepository,
    ItineraryShareRepository,
    NotificationRepository,
    ProfileRepository,
    ReviewRepository,
)
from app.services.analytics_service import AnalyticsService
from app.services.budget_service import BudgetService
from app.services.export_service import ExportService
from app.services.gemini_service import GeminiService
from app.services.itinerary_service import ItineraryService
from app.services.maps_service import GoogleMapsService
from app.services.recommendation_service import RecommendationService
from app.services.review_service import ReviewService
from app.services.share_service import ShareService
from app.services.neon_auth_service import NeonAuthService
from app.services.neon_object_storage_service import NeonObjectStorageService
from app.services.weather_service import OpenWeatherService
from app.services.wikipedia_service import WikipediaService

bearer_scheme = HTTPBearer(auto_error=False, description="Neon Auth access token")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_auth_service(request: Request) -> NeonAuthService:
    return request.app.state.auth_service


def get_token_verifier(request: Request) -> NeonTokenVerifier:
    return request.app.state.token_verifier


def get_object_storage_service(request: Request) -> NeonObjectStorageService:
    return request.app.state.object_storage


def get_maps_service(request: Request) -> GoogleMapsService:
    return request.app.state.maps_service


def get_weather_service(request: Request) -> OpenWeatherService:
    return request.app.state.weather_service


def get_gemini_service(request: Request) -> GeminiService:
    return request.app.state.gemini_service


def get_wikipedia_service(request: Request) -> WikipediaService:
    return request.app.state.wikipedia_service


def get_budget_service(request: Request) -> BudgetService:
    return request.app.state.budget_service


def get_profile_repository(request: Request) -> ProfileRepository:
    return request.app.state.profile_repository


def get_itinerary_repository(request: Request) -> ItineraryRepository:
    return request.app.state.itinerary_repository


def get_itinerary_service(request: Request) -> ItineraryService:
    return request.app.state.itinerary_service


def get_recommendation_service(request: Request) -> RecommendationService:
    return request.app.state.recommendation_service


def get_review_repository(request: Request) -> ReviewRepository:
    return request.app.state.review_repository


def get_notification_repository(request: Request) -> NotificationRepository:
    return request.app.state.notification_repository


def get_share_repository(request: Request) -> ItineraryShareRepository:
    return request.app.state.share_repository


def get_analytics_repository(request: Request) -> AnalyticsRepository:
    return request.app.state.analytics_repository


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


def get_share_service(request: Request) -> ShareService:
    return request.app.state.share_service


def get_export_service(request: Request) -> ExportService:
    return request.app.state.export_service


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("A bearer access token is required.")
    if not credentials.credentials.strip():
        raise AuthenticationError("A bearer access token is required.")
    return credentials.credentials


async def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    verifier: Annotated[NeonTokenVerifier, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    return await verifier.verify(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
DatabaseDep = Annotated[Database, Depends(get_database)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
