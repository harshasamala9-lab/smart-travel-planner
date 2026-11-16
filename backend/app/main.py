"""FastAPI application factory and lifecycle.

The application is deliberately modular: routers own HTTP concerns, services
own integrations and domain rules, repositories own SQL, and this module wires
the layers together once at startup. External services share pooled HTTP
clients and are closed gracefully on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import psycopg
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_router
from app.config import Settings, get_settings
from app.core.exceptions import AppError, DatabaseUnavailableError
from app.core.middleware import install_middlewares
from app.core.security import NeonTokenVerifier
from app.database.connection import Database
from app.database.repositories import (
    AnalyticsRepository,
    ItineraryRepository,
    ItineraryShareRepository,
    NotificationRepository,
    ProfileRepository,
    ReviewRepository,
)
from app.schemas.common import HealthResponse
from app.services.analytics_service import AnalyticsService
from app.services.budget_service import BudgetService
from app.services.export_service import ExportService
from app.services.gemini_service import GeminiService
from app.services.itinerary_service import ItineraryService
from app.services.maps_service import GoogleMapsService
from app.services.neon_auth_service import NeonAuthService
from app.services.neon_object_storage_service import NeonObjectStorageService
from app.services.recommendation_service import RecommendationService
from app.services.review_service import ReviewService
from app.services.share_service import ShareService
from app.services.weather_service import OpenWeatherService
from app.services.wikipedia_service import WikipediaService

logger = logging.getLogger("smart_travel")
access_logger = logging.getLogger("smart_travel.access")

API_DESCRIPTION = """
Production-minded backend for the **Smart Travel Planner**.

### Data honesty
Places, routes, and weather come from Google Maps and OpenWeather. Gemini creates
itinerary structure only from candidate `place_id` values supplied by this API;
unknown places are rejected. All monetary values are clearly marked as estimates
unless a provider explicitly returns a verified live price.

### Security
* Neon Auth (Managed Better Auth) issues short-lived EdDSA JWTs that are
  verified locally against the branch JWKS.
* Passwords are never stored or logged by this service; Neon Auth owns them.
* Every user-owned resource is scoped by the authenticated `sub` claim.
* Share links use high-entropy tokens stored only as SHA-256 hashes; they can expire and be revoked.
* Errors use a stable envelope and include a request ID for support.

### Modules
Authentication, profiles/preferences, Google Places discovery, AI itinerary generation,
reviews, notifications, analytics/CSV reports, sharing, and PDF export.

### Environments
Neon (Lakebase PostgreSQL) is the production database. SQLite is supported only for
isolated tests and offline local development.
"""

TAGS_METADATA = [
    {"name": "Health", "description": "Liveness, readiness, and integration status."},
    {"name": "Authentication", "description": "Neon Auth (Managed Better Auth) email/password and Google OAuth."},
    {"name": "Users", "description": "Profiles, travel preferences, history, and saved places."},
    {"name": "Destinations", "description": "Google Places search, details, photos, and Routes."},
    {"name": "Itineraries", "description": "AI itinerary generation, ownership-scoped CRUD, sharing, and PDF export."},
    {"name": "Recommendations", "description": "Deterministic ranking of real Places results."},
    {"name": "Weather", "description": "Observed weather and honest forecast coverage."},
    {"name": "Reviews", "description": "User reviews for Google Places locations, with ownership rules."},
    {"name": "Notifications", "description": "In-app notification list, read state, and deletion."},
    {"name": "Analytics", "description": "Currency-safe travel analytics and CSV reports."},
    {"name": "Sharing", "description": "Public read-only itinerary views via expiring, revocable tokens."},
]


async def _close_quietly(*resources: Any) -> None:
    closers = []
    for resource in resources:
        close = getattr(resource, "aclose", None)
        if callable(close):
            closers.append(close())
    if closers:
        await asyncio.gather(*closers, return_exceptions=True)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings: Settings = application.state.settings

    database = Database(
        settings.database_dsn,
        pool_min_size=settings.db_pool_min_size,
        pool_max_size=settings.db_pool_max_size,
        pool_timeout_seconds=settings.db_pool_timeout_seconds,
    )
    application.state.database = database

    auth_service = NeonAuthService(settings)
    token_verifier = NeonTokenVerifier(settings)
    object_storage = NeonObjectStorageService(settings)
    maps_service = GoogleMapsService(settings)
    weather_service = OpenWeatherService(settings)
    gemini_service = GeminiService(settings)
    # Keyless open-data discovery (Wikipedia + OpenStreetMap): keeps search,
    # details and itinerary planning working without any provider API key.
    wikipedia_service = WikipediaService(
        timeout_seconds=settings.wikipedia_timeout_seconds,
        geo_cache_ttl_seconds=settings.wikipedia_geo_cache_ttl_seconds,
        extract_cache_ttl_seconds=settings.wikipedia_extract_cache_ttl_seconds,
    )
    budget_service = BudgetService(settings)
    profile_repository = ProfileRepository(database)
    itinerary_repository = ItineraryRepository(database)
    review_repository = ReviewRepository(database)
    notification_repository = NotificationRepository(database)
    share_repository = ItineraryShareRepository(database)
    analytics_repository = AnalyticsRepository(database)
    itinerary_service = ItineraryService(
        settings,
        maps_service=maps_service,
        weather_service=weather_service,
        gemini_service=gemini_service,
        budget_service=budget_service,
        itinerary_repository=itinerary_repository,
        profile_repository=profile_repository,
        notification_repository=notification_repository,
        wikipedia_service=wikipedia_service,
    )
    recommendation_service = RecommendationService(maps_service)
    review_service = ReviewService(
        review_repository=review_repository,
        maps_service=maps_service,
    )
    analytics_service = AnalyticsService(
        analytics_repository=analytics_repository,
        review_repository=review_repository,
    )
    share_service = ShareService(
        itinerary_repository=itinerary_repository,
        share_repository=share_repository,
    )
    export_service = ExportService()

    application.state.auth_service = auth_service
    application.state.token_verifier = token_verifier
    application.state.object_storage = object_storage
    application.state.maps_service = maps_service
    application.state.weather_service = weather_service
    application.state.gemini_service = gemini_service
    application.state.wikipedia_service = wikipedia_service
    application.state.budget_service = budget_service
    application.state.profile_repository = profile_repository
    application.state.itinerary_repository = itinerary_repository
    application.state.itinerary_service = itinerary_service
    application.state.recommendation_service = recommendation_service
    application.state.review_repository = review_repository
    application.state.notification_repository = notification_repository
    application.state.share_repository = share_repository
    application.state.analytics_repository = analytics_repository
    application.state.review_service = review_service
    application.state.analytics_service = analytics_service
    application.state.share_service = share_service
    application.state.export_service = export_service

    try:
        await database.connect()
        if settings.auto_create_schema:
            if database.is_sqlite:
                await database.initialise_sqlite_schema()
                logger.info("SQLite development schema ensured")
            else:
                logger.info(
                    "AUTO_CREATE_SCHEMA is ignored for PostgreSQL; "
                    "apply backend/neon/schema.sql on the Neon branch"
                )

        configured = settings.integration_status()
        logger.info(
            "Smart Travel Planner API started env=%s version=%s integrations=%s",
            settings.app_env,
            settings.app_version,
            ",".join(name for name, ready in configured.items() if ready) or "none",
        )
        for warning in settings.integration_warnings:
            logger.warning(
                "Optional integration not configured: %s (related endpoints "
                "will return an explicit unavailable response)",
                warning,
            )
        yield
    finally:
        await _close_quietly(
            auth_service,
            token_verifier,
            maps_service,
            weather_service,
            gemini_service,
            wikipedia_service,
        )
        await database.close()
        logger.info("Smart Travel Planner API stopped")


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": jsonable_encoder(details),
                "request_id": _request_id(request),
            }
        },
        headers=headers,
    )
    response.headers.setdefault("X-Request-ID", _request_id(request))
    return response


def _configure_logging(settings: Settings) -> None:
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=False,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured application instance.

    Passing ``settings`` is useful for tests and for hosting multiple
    environments in one process. The default reads environment variables and
    ``backend/.env``.
    """

    app_settings = settings or get_settings()
    _configure_logging(app_settings)

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=API_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={"name": "Smart Travel Planner API"},
        swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    )
    application.state.settings = app_settings
    frontend_dist = Path(app_settings.frontend_dist_path)
    has_spa = (frontend_dist / "index.html").is_file()

    install_middlewares(application, app_settings)
    application.add_middleware(GZipMiddleware, minimum_size=1024)
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            access_logger.error(
                "Application error %s request_id=%s: %s",
                exc.code,
                _request_id(request),
                exc.message,
            )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for item in exc.errors():
            safe = {
                "type": item.get("type"),
                "loc": list(item.get("loc", ())),
                "msg": item.get("msg"),
            }
            if "ctx" in item:
                safe["ctx"] = item["ctx"]
            errors.append(safe)
        return _error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="The request contains invalid or missing fields.",
            details={"errors": errors},
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            401: "authentication_required",
            403: "permission_denied",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limit_exceeded",
        }.get(exc.status_code, "http_error")
        message = (
            exc.detail
            if isinstance(exc.detail, str) and exc.detail
            else "The requested operation failed."
        )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
            headers=dict(exc.headers or {}),
        )

    @application.exception_handler(sqlite3.IntegrityError)
    @application.exception_handler(psycopg.IntegrityError)
    async def handle_integrity_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        access_logger.warning(
            "Database constraint conflict request_id=%s type=%s",
            _request_id(request),
            type(exc).__name__,
        )
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            message="The request conflicts with existing data.",
        )

    @application.exception_handler(DatabaseUnavailableError)
    async def handle_database_unavailable(
        request: Request, exc: DatabaseUnavailableError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=exc.code,
            message=exc.message,
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        access_logger.exception(
            "Unhandled server error request_id=%s", _request_id(request)
        )
        return _error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected server error occurred.",
        )

    @application.get(
        "/",
        tags=["Health"],
        summary="API index and documentation links",
    )
    async def index() -> Any:
        if has_spa:
            return FileResponse(
                frontend_dist / "index.html",
                headers={"Cache-Control": "no-cache"},
            )
        prefix = app_settings.api_v1_prefix
        return {
            "name": app_settings.app_name,
            "version": app_settings.app_version,
            "environment": app_settings.app_env,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
            "readiness": "/health/ready",
            "api": prefix,
        }

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Liveness and integration configuration status",
        description=(
            "Process liveness. Integration flags indicate whether credentials are "
            "configured; they do not spend quota by calling third parties."
        ),
    )
    async def health() -> HealthResponse:
        configured = app_settings.integration_status()
        return HealthResponse(
            status="ok",
            version=app_settings.app_version,
            environment=app_settings.app_env,
            checks={
                "integrations": configured,
                "database_dialect": "sqlite" if app_settings.sqlite_database else "postgresql",
            },
        )

    @application.get(
        "/health/ready",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Readiness including a database round trip",
        responses={503: {"description": "Database or required schema is unavailable"}},
    )
    async def readiness(request: Request) -> HealthResponse | JSONResponse:
        checks: dict[str, Any] = {
            "integrations": app_settings.integration_status(),
        }
        try:
            database_check = await request.app.state.database.check_health()
            checks["database"] = database_check
            return HealthResponse(
                status="ready",
                version=app_settings.app_version,
                environment=app_settings.app_env,
                checks=checks,
            )
        except DatabaseUnavailableError:
            checks["database"] = {"status": "down"}
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "version": app_settings.app_version,
                    "environment": app_settings.app_env,
                    "checks": jsonable_encoder(checks),
                },
            )

    if has_spa:
        # Single-container deployment: the React build is served by FastAPI.
        # Hashed build assets are immutable; every other unknown path falls
        # back to index.html so client-side routes survive a hard refresh.
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            application.mount(
                "/assets",
                StaticFiles(directory=assets_dir),
                name="spa-assets",
            )

        @application.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            if full_path.startswith(
                ("api/", "health", "docs", "redoc", "openapi.json")
            ):
                raise StarletteHTTPException(status_code=404, detail="Not found")
            candidate = (frontend_dist / full_path).resolve()
            root = frontend_dist.resolve()
            if candidate.is_file() and (candidate == root or root in candidate.parents):
                return FileResponse(
                    candidate,
                    headers={"Cache-Control": "public, max-age=86400"},
                )
            return FileResponse(
                frontend_dist / "index.html",
                headers={"Cache-Control": "no-cache"},
            )

    return application


app = create_app()
