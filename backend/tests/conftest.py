"""Shared offline fixtures.

External APIs are faked at the service boundary so tests exercise real routing,
validation, persistence, authorization, and response models without spending
quota or requiring secrets.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.core.security import AuthenticatedUser
from app.main import create_app
from app.models.enums import ActivityCategory, TravelMode
from app.schemas.ai import AIActivity, AIDay, AIItinerary
from app.services.itinerary_service import ItineraryService
from app.services.neon_auth_service import AuthResult, AuthSession
from app.services.recommendation_service import RecommendationService
from app.services.review_service import ReviewService
from app.utils.time import utc_now_iso

TEST_JWT_SECRET = "test-jwt-secret-that-is-long-enough-for-hs256-signing"
TEST_AUTH_BASE_URL = "https://auth-host.neonauth.region.aws.neon.tech"


@pytest.fixture
def start_date() -> date:
    return date.today() + timedelta(days=30)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        debug=True,
        database_url=SecretStr(f"sqlite:///{tmp_path / 'smart_travel_test.db'}"),
        auto_create_schema=True,
        neon_auth_base_url=TEST_AUTH_BASE_URL,
        neon_auth_jwks_url=f"{TEST_AUTH_BASE_URL}/.well-known/jwks.json",
        auth_hs256_secret=SecretStr(TEST_JWT_SECRET),
        allowed_hosts="testserver,localhost,127.0.0.1",
        cors_origins="http://localhost:5173",
        auth_rate_limit_requests=1000,
        auth_rate_limit_window_seconds=60,
        request_timeout_seconds=30,
    )


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user(user_id: uuid.UUID) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        email="traveler@example.com",
        role="authenticated",
        claims={
            "sub": str(user_id),
            "email": "traveler@example.com",
            "name": "Test Traveler",
            "role": "authenticated",
            "aud": TEST_AUTH_BASE_URL,
            "iss": TEST_AUTH_BASE_URL,
        },
    )


@pytest.fixture
def token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "traveler@example.com",
            "name": "Test Traveler",
            "role": "authenticated",
            "aud": TEST_AUTH_BASE_URL,
            "iss": TEST_AUTH_BASE_URL,
            "iat": now.timestamp(),
            "exp": now.timestamp() + 900,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def destination_place() -> dict[str, Any]:
    return {
        "place_id": "dest_kyoto",
        "name": "Kyoto",
        "formatted_address": "Kyoto, Japan",
        "latitude": 35.0116,
        "longitude": 135.7681,
        "rating": 4.7,
        "user_rating_count": 120_000,
        "price_level": "PRICE_LEVEL_MODERATE",
        "types": ["locality", "tourist_attraction"],
        "category": None,
        "open_now": True,
        "business_status": "OPERATIONAL",
        "google_maps_uri": "https://maps.google.com/?cid=kyoto",
        "photo_names": ["places/dest_kyoto/photos/photo1"],
        "opening_hours": [],
        "current_opening_hours": [],
        "website_uri": "https://kyoto.travel",
        "national_phone_number": None,
        "editorial_summary": "Historic city in Japan.",
    }


def place(
    place_id: str,
    name: str,
    *,
    category: ActivityCategory,
    latitude: float = 35.0,
    longitude: float = 135.7,
    rating: float = 4.5,
    reviews: int = 500,
    types: list[str] | None = None,
    price_level: str | None = "PRICE_LEVEL_MODERATE",
    open_now: bool = True,
) -> dict[str, Any]:
    return {
        "place_id": place_id,
        "name": name,
        "formatted_address": f"{name}, Kyoto, Japan",
        "latitude": latitude,
        "longitude": longitude,
        "rating": rating,
        "user_rating_count": reviews,
        "price_level": price_level,
        "types": types or ["tourist_attraction"],
        "category": category.value,
        "open_now": open_now,
        "business_status": "OPERATIONAL",
        "google_maps_uri": f"https://maps.google.com/?cid={place_id}",
        "photo_names": [f"places/{place_id}/photos/photo1"],
        "opening_hours": ["Monday: 9:00 AM – 5:00 PM"],
        "current_opening_hours": ["Monday: 9:00 AM – 5:00 PM"],
        "website_uri": f"https://example.com/{place_id}",
        "national_phone_number": "+81-75-000-0000",
        "editorial_summary": None,
    }


def wiki_attraction(
    pageid: int,
    name: str,
    *,
    latitude: float = 35.0,
    longitude: float = 135.7,
    description: str | None = None,
    image_url: str | None = None,
) -> dict[str, Any]:
    return {
        "place_id": f"wiki-{pageid}",
        "name": name,
        "formatted_address": f"{name} (Kyoto)",
        "latitude": latitude,
        "longitude": longitude,
        "rating": None,
        "user_rating_count": None,
        "price_level": None,
        "types": ["heritage", "wikipedia", "tourist_attraction"],
        "category": ActivityCategory.ATTRACTION.value,
        "open_now": None,
        "business_status": "OPERATIONAL",
        "google_maps_uri": f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}",
        "photo_names": [],
        "opening_hours": [],
        "description": description or f"About {name}.",
        "editorial_summary": description or f"About {name}.",
        "country": None,
        "image_url": image_url,
        "image_alt": name,
        "image_credit": "Wikipedia / Wikimedia Commons contributors",
        "best_time": None,
        "travel_type": "heritage",
        "source": "Wikipedia (open data)",
    }


class FakeMapsService:
    is_configured = True

    def __init__(self) -> None:
        self.destination = destination_place()
        self.attractions = [
            place(
                "attr_1",
                "Kinkaku-ji",
                category=ActivityCategory.ATTRACTION,
                latitude=35.0394,
                longitude=135.7292,
                rating=4.8,
                reviews=50_000,
                types=["tourist_attraction", "historical_landmark"],
            ),
            place(
                "attr_2",
                "Fushimi Inari",
                category=ActivityCategory.ATTRACTION,
                latitude=34.9671,
                longitude=135.7727,
                rating=4.7,
                reviews=80_000,
                types=["tourist_attraction", "place_of_worship"],
            ),
            place(
                "attr_3",
                "Arashiyama Bamboo Grove",
                category=ActivityCategory.ATTRACTION,
                latitude=35.0170,
                longitude=135.6710,
                rating=4.6,
                reviews=40_000,
                types=["park", "tourist_attraction"],
            ),
        ]
        self.restaurants = [
            place(
                "rest_1",
                "Nishiki Market",
                category=ActivityCategory.RESTAURANT,
                latitude=35.0050,
                longitude=135.7649,
                rating=4.4,
                reviews=20_000,
                types=["restaurant", "market"],
            ),
            place(
                "rest_2",
                "Gion Karyo",
                category=ActivityCategory.RESTAURANT,
                latitude=35.0037,
                longitude=135.7788,
                rating=4.6,
                reviews=5_000,
                types=["restaurant"],
                price_level="PRICE_LEVEL_EXPENSIVE",
            ),
        ]
        self.hotels = [
            place(
                "hotel_1",
                "Kyoto Central Hotel",
                category=ActivityCategory.HOTEL,
                latitude=34.9858,
                longitude=135.7588,
                rating=4.5,
                reviews=1_200,
                types=["lodging"],
            ),
        ]
        self.route_calls = 0

    async def aclose(self) -> None:
        return None

    async def search_destinations(
        self, query: str, *, limit: int = 10, language: str | None = None
    ) -> list[dict[str, Any]]:
        return [self.destination][:limit]

    async def get_place_details(self, place_id: str) -> dict[str, Any]:
        for item in [self.destination, *self.attractions, *self.restaurants, *self.hotels]:
            if item["place_id"] == place_id:
                return item
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Place not found.")

    async def nearby_places(
        self,
        *,
        latitude: float,
        longitude: float,
        included_types: list[str],
        limit: int = 15,
        radius_m: int = 10_000,
        category: ActivityCategory | None = None,
    ) -> list[dict[str, Any]]:
        if category == ActivityCategory.ATTRACTION:
            return self.attractions[:limit]
        if category == ActivityCategory.RESTAURANT:
            return self.restaurants[:limit]
        if category == ActivityCategory.HOTEL:
            return self.hotels[:limit]
        return []

    async def resolve_destination(
        self, destination: str, destination_place_id: str | None = None
    ) -> dict[str, Any]:
        return dict(self.destination)

    async def resolve_location(self, location: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": location.get("name") or "Resolved place",
            "address": location.get("address"),
            "latitude": 35.0,
            "longitude": 135.7,
            "place_id": location.get("place_id"),
        }

    async def compute_route(
        self,
        *,
        origin: dict[str, Any],
        destination: dict[str, Any],
        travel_mode: TravelMode,
        include_steps: bool = False,
    ) -> dict[str, Any]:
        self.route_calls += 1
        return {
            "origin": origin,
            "destination": destination,
            "travel_mode": travel_mode.value,
            "distance_meters": 2400,
            "distance_km": 2.4,
            "duration_seconds": 600,
            "duration_minutes": 10.0,
            "polyline": "abc123",
            "steps": [],
            "calculated_at": datetime.now(timezone.utc),
        }

    async def fetch_photo(
        self, photo_name: str, *, max_width: int = 1200
    ) -> tuple[bytes, str]:
        return b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg"

    async def geocode(self, address: str) -> dict[str, Any]:
        return {
            "name": address,
            "address": address,
            "latitude": 35.0,
            "longitude": 135.7,
            "place_id": "geocoded_1",
        }


class FakeWeatherService:
    is_configured = True

    def __init__(self, start: date) -> None:
        self.start = start

    async def aclose(self) -> None:
        return None

    def payload(
        self,
        *,
        name: str,
        latitude: float,
        longitude: float,
        start_date: date | None,
        end_date: date | None,
        units: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "destination": name,
            "country": "JP",
            "latitude": latitude,
            "longitude": longitude,
            "units": units,
            "current": {
                "observed_at": now,
                "temperature": 18.0,
                "feels_like": 18.0,
                "temp_min": 16.0,
                "temp_max": 20.0,
                "humidity": 60,
                "pressure": 1012,
                "wind_speed": 3.0,
                "wind_degrees": 180,
                "condition": {"main": "Clear", "description": "clear sky", "icon": "01d"},
                "sunrise": now,
                "sunset": now,
                "units": units,
            },
            "forecast": [
                {
                    "date": self.start,
                    "temp_min": 15.0,
                    "temp_max": 21.0,
                    "average_temperature": 18.0,
                    "humidity": 58,
                    "precipitation_probability": 10.0,
                    "condition": {
                        "main": "Clear",
                        "description": "clear sky",
                        "icon": "01d",
                    },
                    "summary": "Clear skies",
                }
            ],
            "requested_start_date": start_date,
            "requested_end_date": end_date,
            "forecast_covers_requested_dates": True,
            "suggestions": ["Carry water on sunny days."],
            "source": "OpenWeather API",
            "disclaimer": "Forecast data covers the provider's available horizon only.",
            "fetched_at": now,
            "attribution": "Weather data by OpenWeather",
        }

    async def get_weather(
        self,
        destination: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        units: str = "metric",
    ) -> dict[str, Any]:
        return self.payload(
            name=destination,
            latitude=35.0,
            longitude=135.7,
            start_date=start_date,
            end_date=end_date,
            units=str(getattr(units, "value", units)),
        )

    async def get_weather_for_coordinates(
        self,
        *,
        name: str,
        latitude: float,
        longitude: float,
        start_date: date | None = None,
        end_date: date | None = None,
        units: str = "metric",
    ) -> dict[str, Any]:
        return self.payload(
            name=name,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            units=str(getattr(units, "value", units)),
        )


class FakeGeminiService:
    """Returns a valid two-day plan; can be told to fail validation first."""

    def __init__(self, start: date, *, invalid_attempts: int = 0) -> None:
        self.start = start
        self.invalid_attempts = invalid_attempts
        self.prompts: list[str] = []
        self.calls = 0

    @property
    def model(self) -> str:
        return "gemini-test"

    @property
    def is_configured(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    def _valid_plan(self) -> AIItinerary:
        return AIItinerary(
            title="Kyoto in Bloom",
            summary="Two days exploring Kyoto's temples and food markets.",
            recommended_hotel_place_id="hotel_1",
            days=[
                AIDay(
                    day_number=1,
                    date=self.start,
                    title="Temples and markets",
                    summary="Start early to avoid crowds.",
                    activities=[
                        AIActivity(
                            place_id="attr_1",
                            start_time="09:00",
                            end_time="11:00",
                            description="Visit the golden pavilion.",
                            estimated_cost=5,
                        ),
                        AIActivity(
                            place_id="rest_1",
                            start_time="12:00",
                            end_time="13:00",
                            description="Lunch at the market.",
                            estimated_cost=15,
                        ),
                        AIActivity(
                            place_id="attr_2",
                            start_time="14:00",
                            end_time="16:00",
                            description="Walk the torii gates.",
                            estimated_cost=0,
                        ),
                    ],
                ),
                AIDay(
                    day_number=2,
                    date=self.start + timedelta(days=1),
                    title="Arashiyama and Gion",
                    summary="A slower day west of the city.",
                    activities=[
                        AIActivity(
                            place_id="attr_3",
                            start_time="09:30",
                            end_time="11:30",
                            description="Explore the bamboo grove.",
                            estimated_cost=0,
                        ),
                        AIActivity(
                            place_id="rest_2",
                            start_time="12:30",
                            end_time="13:30",
                            description="Seasonal lunch.",
                            estimated_cost=25,
                        ),
                    ],
                ),
            ],
            tips=["Buy a transit pass.", "Reserve restaurants ahead."],
        )

    def _invalid_plan(self) -> AIItinerary:
        plan = self._valid_plan()
        bad_day = plan.days[0].model_copy(
            update={
                "activities": [
                    AIActivity(
                        place_id="invented_place",
                        start_time="09:00",
                        end_time="10:00",
                        description="A hallucinated location.",
                        estimated_cost=0,
                    )
                ]
            }
        )
        return plan.model_copy(update={"days": [bad_day, plan.days[1]]})

    async def generate_itinerary(self, prompt: str) -> AIItinerary:
        self.prompts.append(prompt)
        self.calls += 1
        if self.calls <= self.invalid_attempts:
            return self._invalid_plan()
        return self._valid_plan()


class FakeAuthService:
    """Fake for the Neon Auth service boundary."""

    is_configured = True

    def __init__(self, user_id: uuid.UUID | None = None) -> None:
        self.user_id = user_id or uuid.uuid4()
        self.logged_out_tokens: list[str] = []

    async def aclose(self) -> None:
        return None

    def _result(self, *, full_name: str = "Test Traveler") -> AuthResult:
        session = AuthSession(
            access_token="fake-access-token",
            refresh_token="fake-refresh-token",
            token_type="bearer",
            expires_in=900,
            expires_at=9999999999,
        )
        return AuthResult(
            user={
                "id": str(self.user_id),
                "email": "traveler@example.com",
                "email_confirmed": True,
                "provider": "email",
                "full_name": full_name,
                "avatar_url": None,
                "created_at": utc_now_iso(),
            },
            session=session,
        )

    async def register(self, *, email: str, password: str, full_name: str) -> AuthResult:
        return self._result(full_name=full_name)

    async def login(self, *, email: str, password: str) -> AuthResult:
        return self._result()

    async def refresh(self, session_token: str) -> AuthResult:
        return self._result()

    async def describe_user(self, session_token: str) -> dict[str, Any]:
        return self._result().user

    async def logout(self, session_token: str) -> None:
        self.logged_out_tokens.append(session_token)

    async def google_authorization(self, *, redirect_to: str) -> dict[str, str]:
        return {
            "authorization_url": (
                "https://auth-host.neonauth.region.aws.neon.tech/sign-in/social"
                f"?provider=google&callbackURL={redirect_to}"
            ),
            "provider": "google",
            "redirect_to": redirect_to,
        }


class FakeWikipediaService:
    """Keyless open-data discovery fake; empty by default, seeded per test."""

    is_configured = True

    def __init__(
        self,
        *,
        geocode_result: dict[str, Any] | None = None,
        attractions: list[dict[str, Any]] | None = None,
        articles: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        self.geocode_result = geocode_result
        self.attractions = attractions or []
        self.articles = articles or {}
        self.geocode_calls: list[str] = []
        self.nearby_calls: list[dict[str, Any]] = []
        self.article_calls: list[int] = []

    async def aclose(self) -> None:
        return None

    async def geocode(self, query: str) -> dict[str, Any] | None:
        self.geocode_calls.append(query)
        return self.geocode_result

    async def nearby_attractions(
        self,
        *,
        name: str,
        latitude: float | None,
        longitude: float | None,
        limit: int = 12,
        radius_m: int = 10_000,
    ) -> list[dict[str, Any]]:
        self.nearby_calls.append(
            {
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "limit": limit,
                "radius_m": radius_m,
            }
        )
        return self.attractions[:limit]

    async def article_summary(self, pageid: int) -> dict[str, Any] | None:
        self.article_calls.append(pageid)
        return self.articles.get(pageid)


@pytest.fixture
def fake_wikipedia() -> FakeWikipediaService:
    return FakeWikipediaService()


@pytest.fixture
def fake_maps() -> FakeMapsService:
    return FakeMapsService()


@pytest.fixture
def fake_weather(start_date: date) -> FakeWeatherService:
    return FakeWeatherService(start_date)


@pytest.fixture
def fake_gemini(start_date: date) -> FakeGeminiService:
    return FakeGeminiService(start_date)


@pytest.fixture
def fake_auth() -> FakeAuthService:
    return FakeAuthService()


@pytest.fixture
def client(
    settings: Settings,
    user: AuthenticatedUser,
    fake_maps: FakeMapsService,
    fake_weather: FakeWeatherService,
    fake_gemini: FakeGeminiService,
    fake_auth: FakeAuthService,
    fake_wikipedia: FakeWikipediaService,
):
    application = create_app(settings)
    with TestClient(application) as test_client:
        application.state.maps_service = fake_maps
        application.state.weather_service = fake_weather
        application.state.gemini_service = fake_gemini
        application.state.wikipedia_service = fake_wikipedia
        application.state.auth_service = fake_auth
        application.state.itinerary_service = ItineraryService(
            settings,
            maps_service=fake_maps,
            weather_service=fake_weather,
            gemini_service=fake_gemini,
            budget_service=application.state.budget_service,
            itinerary_repository=application.state.itinerary_repository,
            profile_repository=application.state.profile_repository,
            notification_repository=application.state.notification_repository,
            wikipedia_service=fake_wikipedia,
        )
        application.state.recommendation_service = RecommendationService(fake_maps)
        application.state.review_service = ReviewService(
            review_repository=application.state.review_repository,
            maps_service=fake_maps,
        )
        yield test_client
