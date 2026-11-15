"""Unit tests for external integrations using local HTTP transports."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.core.exceptions import (
    AIGenerationError,
    AuthenticationError,
    ConflictError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)
from app.models.enums import TravelMode, WeatherUnits
from app.schemas.ai import AIActivity, AIDay, AIItinerary
from app.services.gemini_service import GeminiService
from app.services.maps_service import GoogleMapsService
from app.services.neon_auth_service import SESSION_COOKIE, NeonAuthService
from app.services.weather_service import OpenWeatherService


def _settings(tmp_path, **updates) -> Settings:
    values = {
        "app_env": "test",
        "database_url": SecretStr(f"sqlite:///{tmp_path / 'integration.db'}"),
        "google_maps_api_key": SecretStr("maps-test-key"),
        "google_maps_language": "en",
        "openweather_api_key": SecretStr("weather-test-key"),
        "weather_cache_ttl_seconds": 600,
        "neon_auth_base_url": "https://auth-host.neonauth.region.aws.neon.tech",
        "neon_auth_origin": "http://localhost:5173",
        "gemini_api_key": SecretStr("gemini-test-key"),
        "gemini_model": "gemini-test-model",
    }
    values.update(updates)
    # _env_file=None keeps the developer's local .env (real Neon URLs, keys)
    # from leaking into unit tests; every value is set explicitly above.
    return Settings(_env_file=None, **values)


def _maps_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _place_payload(
    place_id: str = "place_1",
    *,
    name: str = "Test Place",
    closed: bool = False,
) -> dict:
    return {
        "id": place_id,
        "displayName": {"text": name},
        "formattedAddress": "1 Test Street",
        "location": {"latitude": 35.0, "longitude": 135.7},
        "rating": 4.6,
        "userRatingCount": 1250,
        "priceLevel": "PRICE_LEVEL_MODERATE",
        "types": ["tourist_attraction"],
        "businessStatus": "CLOSED_PERMANENTLY" if closed else "OPERATIONAL",
        "googleMapsUri": "https://maps.google.com/?cid=1",
        "currentOpeningHours": {
            "openNow": True,
            "weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM"],
        },
        "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM"]},
        "photos": [{"name": "places/place_1/photos/photo_1"}],
        "websiteUri": "https://example.com",
        "nationalPhoneNumber": "+1 555 0100",
        "editorialSummary": {"text": "A useful place."},
    }


@pytest.mark.asyncio
async def test_maps_text_search_normalisation(tmp_path):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["mask"] = request.headers.get("x-goog-fieldmask")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"places": [_place_payload()]})

    client = _maps_client(handler)
    service = GoogleMapsService(_settings(tmp_path), client=client)
    try:
        results = await service.search_destinations("Kyoto", limit=3)
    finally:
        await service.aclose()
        await client.aclose()

    assert seen["path"] == "/v1/places:searchText"
    assert seen["key"] == "maps-test-key"
    assert "places.id" in seen["mask"]
    assert seen["body"]["maxResultCount"] == 3
    assert results[0]["place_id"] == "place_1"
    assert results[0]["name"] == "Test Place"
    assert results[0]["latitude"] == 35.0
    assert results[0]["opening_hours"] == ["Monday: 9:00 AM – 5:00 PM"]
    assert results[0]["current_opening_hours"] == ["Monday: 9:00 AM – 5:00 PM"]


@pytest.mark.asyncio
async def test_maps_nearby_filters_closed_places(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/places:searchNearby"
        body = json.loads(request.content)
        assert body["locationRestriction"]["circle"]["radius"] == 10000
        assert body["includedTypes"] == ["restaurant"]
        return httpx.Response(
            200,
            json={
                "places": [
                    _place_payload("open_place"),
                    _place_payload("closed_place", closed=True),
                ]
            },
        )

    client = _maps_client(handler)
    service = GoogleMapsService(_settings(tmp_path), client=client)
    try:
        places = await service.nearby_places(
            latitude=35.0,
            longitude=135.7,
            included_types=["restaurant"],
            limit=10,
            radius_m=10_000,
        )
    finally:
        await service.aclose()
        await client.aclose()
    assert [item["place_id"] for item in places] == ["open_place"]


@pytest.mark.asyncio
async def test_maps_details_and_not_found(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/missing"):
            return httpx.Response(404, json={"error": {"message": "not found"}})
        return httpx.Response(200, json=_place_payload("details_1"))

    client = _maps_client(handler)
    service = GoogleMapsService(_settings(tmp_path), client=client)
    try:
        place = await service.get_place_details("details_1")
        assert place["place_id"] == "details_1"
        with pytest.raises(NotFoundError):
            await service.get_place_details("missing")
    finally:
        await service.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_maps_geocode_and_route(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/maps/api/geocode/json":
            return httpx.Response(
                200,
                json={
                    "status": "OK",
                    "results": [
                        {
                            "formatted_address": "Kyoto, Japan",
                            "geometry": {"location": {"lat": 35.0, "lng": 135.7}},
                            "place_id": "geo_1",
                        }
                    ],
                },
            )
        if request.url.path == "/directions/v2:computeRoutes":
            body = json.loads(request.content)
            assert body["travelMode"] == "DRIVE"
            assert body["routingPreference"] == "TRAFFIC_AWARE"
            return httpx.Response(
                200,
                json={
                    "routes": [
                        {
                            "distanceMeters": 12500,
                            "duration": "1800s",
                            "polyline": {"encodedPolyline": "encoded"},
                            "legs": [
                                {
                                    "steps": [
                                        {
                                            "navigationInstruction": {
                                                "instructions": "Head north"
                                            },
                                            "distanceMeters": 500,
                                            "staticDuration": "120s",
                                        }
                                    ]
                                }
                            ],
                        }
                    ]
                },
            )
        return httpx.Response(500)

    client = _maps_client(handler)
    service = GoogleMapsService(_settings(tmp_path), client=client)
    try:
        geocoded = await service.geocode("Kyoto")
        assert geocoded["latitude"] == 35.0
        assert geocoded["place_id"] == "geo_1"

        route = await service.compute_route(
            origin={
                "name": "A",
                "address": None,
                "latitude": 35.0,
                "longitude": 135.7,
                "place_id": None,
            },
            destination={
                "name": "B",
                "address": None,
                "latitude": 35.1,
                "longitude": 135.8,
                "place_id": None,
            },
            travel_mode=TravelMode.DRIVE,
            include_steps=True,
        )
    finally:
        await service.aclose()
        await client.aclose()

    assert route["distance_meters"] == 12500
    assert route["distance_km"] == 12.5
    assert route["duration_seconds"] == 1800
    assert route["polyline"] == "encoded"
    assert route["steps"][0]["instruction"] == "Head north"


@pytest.mark.asyncio
async def test_maps_photo_proxy_and_key_validation(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/media")
        assert request.url.params["maxWidthPx"] == "900"
        return httpx.Response(
            200,
            content=b"jpeg-bytes",
            headers={"Content-Type": "image/jpeg; charset=binary"},
        )

    client = _maps_client(handler)
    service = GoogleMapsService(_settings(tmp_path), client=client)
    try:
        content, media_type = await service.fetch_photo(
            "places/place_1/photos/photo_1", max_width=900
        )
        assert content == b"jpeg-bytes"
        assert media_type == "image/jpeg"
        with pytest.raises(NotFoundError):
            await service.fetch_photo("../../etc/passwd")
    finally:
        await service.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_maps_handles_upstream_failure_and_missing_key(tmp_path):
    client = _maps_client(lambda request: httpx.Response(500, json={}))
    service = GoogleMapsService(_settings(tmp_path), client=client)
    try:
        with pytest.raises(ExternalServiceError):
            await service.search_destinations("Kyoto")
    finally:
        await service.aclose()
        await client.aclose()

    without_key = GoogleMapsService(
        _settings(tmp_path, google_maps_api_key=None), client=client
    )
    try:
        with pytest.raises(ServiceUnavailableError):
            await without_key.search_destinations("Kyoto")
    finally:
        await without_key.aclose()


def _weather_handler(requests: list[str], *, forecast_error: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/geo/1.0/direct":
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "Kyoto",
                        "country": "JP",
                        "lat": 35.0,
                        "lon": 135.7,
                    }
                ],
            )
        if request.url.path == "/data/2.5/weather":
            return httpx.Response(
                200,
                json={
                    "dt": 1_700_000_000,
                    "weather": [
                        {"main": "Rain", "description": "light rain", "icon": "10d"}
                    ],
                    "main": {
                        "temp": 14.5,
                        "feels_like": 13.0,
                        "temp_min": 12.0,
                        "temp_max": 16.0,
                        "humidity": 80,
                        "pressure": 1008,
                    },
                    "wind": {"speed": 11.0, "deg": 210},
                    "sys": {"sunrise": 1_699_990_000, "sunset": 1_700_030_000},
                },
            )
        if request.url.path == "/data/2.5/forecast":
            if forecast_error:
                return httpx.Response(500, json={})
            base = datetime.combine(
                date.today(), datetime.min.time(), tzinfo=timezone.utc
            ) + timedelta(hours=12)
            items = []
            for day_offset in (0, 1):
                dt = base + timedelta(days=day_offset)
                items.append(
                    {
                        "dt": int(dt.timestamp()),
                        "main": {
                            "temp": 15.0 + day_offset,
                            "temp_min": 10.0 + day_offset,
                            "temp_max": 18.0 + day_offset,
                            "humidity": 60,
                        },
                        "weather": [{"main": "Clear", "description": "clear sky"}],
                        "pop": 0.1,
                    }
                )
            return httpx.Response(
                200,
                json={"city": {"timezone": 0}, "list": items},
            )
        return httpx.Response(404)

    return handler


@pytest.mark.asyncio
async def test_weather_aggregation_and_cache(tmp_path):
    requests: list[str] = []
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(_weather_handler(requests))
    )
    service = OpenWeatherService(_settings(tmp_path), client=client)
    try:
        first = await service.get_weather(
            "Kyoto",
            start_date=date.today(),
            end_date=date.today(),
            units=WeatherUnits.METRIC,
        )
        second = await service.get_weather(
            "Kyoto",
            start_date=date.today(),
            end_date=date.today(),
            units=WeatherUnits.METRIC,
        )
    finally:
        await service.aclose()
        await client.aclose()

    assert first["forecast_covers_requested_dates"] is True
    assert first["current"]["condition"]["description"] == "Light rain"
    assert first["current"]["temperature"] == 14.5
    assert first["forecast"][0]["date"] == date.today()
    assert any("Rain is possible" in item for item in first["suggestions"])
    assert first["fetched_at"] == second["fetched_at"]
    # Geocoding and current/forecast are all cached by destination/coordinates.
    assert requests.count("/geo/1.0/direct") == 1
    assert requests.count("/data/2.5/weather") == 1
    assert requests.count("/data/2.5/forecast") == 1


@pytest.mark.asyncio
async def test_weather_forecast_failure_is_honest(tmp_path):
    requests: list[str] = []
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            _weather_handler(requests, forecast_error=True)
        )
    )
    service = OpenWeatherService(_settings(tmp_path), client=client)
    try:
        payload = await service.get_weather("Kyoto")
    finally:
        await service.aclose()
        await client.aclose()
    assert payload["forecast"] == []
    assert payload["forecast_covers_requested_dates"] is None
    assert any("temporarily unavailable" in item for item in payload["suggestions"])


@pytest.mark.asyncio
async def test_weather_geocode_not_found_and_missing_key(tmp_path):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    )
    service = OpenWeatherService(_settings(tmp_path), client=client)
    try:
        with pytest.raises(NotFoundError):
            await service.get_weather("Nowhere")
    finally:
        await service.aclose()
        await client.aclose()

    no_key = OpenWeatherService(
        _settings(tmp_path, openweather_api_key=None), client=client
    )
    try:
        with pytest.raises(ServiceUnavailableError):
            await no_key.get_weather("Kyoto")
    finally:
        await no_key.aclose()


AUTH_BASE = "https://auth-host.neonauth.region.aws.neon.tech"
_TEST_USER = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "a@example.com",
    "emailVerified": True,
    "name": "A",
    "image": None,
    "createdAt": "2026-01-01T00:00:00Z",
}


def _access_jwt() -> str:
    import time

    import jwt as pyjwt

    now = int(time.time())
    return pyjwt.encode(
        {"sub": _TEST_USER["id"], "exp": now + 900, "iat": now},
        "probe-secret",
        algorithm="HS256",
    )


def _auth_handler(seen: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "path": request.url.path,
                "method": request.method,
                "body": json.loads(request.content or b"{}"),
                "origin": request.headers.get("origin"),
                "cookie": request.headers.get("cookie"),
            }
        )
        if request.url.path == "/sign-up/email":
            return httpx.Response(
                200,
                json={"token": "raw-token-1", "user": _TEST_USER},
                headers={"Set-Cookie": f"{SESSION_COOKIE}=signed-session-1; Path=/"},
            )
        if request.url.path == "/sign-in/email":
            return httpx.Response(
                200,
                json={"redirect": False, "token": "raw-token-1", "user": _TEST_USER},
                headers={"Set-Cookie": f"{SESSION_COOKIE}=signed-session-1; Path=/"},
            )
        if request.url.path == "/token":
            return httpx.Response(200, json={"token": _access_jwt()})
        if request.url.path == "/get-session":
            return httpx.Response(
                200,
                json={
                    "session": {"token": "session-token-1"},
                    "user": _TEST_USER,
                },
            )
        if request.url.path == "/sign-out":
            return httpx.Response(200, json={"success": True})
        if request.url.path == "/sign-in/social":
            return httpx.Response(
                200,
                json={"url": f"{AUTH_BASE}/callback/google", "redirect": False},
            )
        return httpx.Response(400, json={"message": "bad request"})

    return handler


@pytest.mark.asyncio
async def test_neon_auth_flow(tmp_path):
    seen: list[dict] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(_auth_handler(seen)))
    service = NeonAuthService(_settings(tmp_path), client=client)
    try:
        registered = await service.register(
            email="a@example.com", password="Password1", full_name="A"
        )
        assert registered.user["id"] == "11111111-1111-1111-1111-111111111111"
        assert registered.user["full_name"] == "A"
        assert registered.session is not None
        # The signed cookie value, not the body token, is the session token
        # handed to clients (verified against live Better Auth).
        assert registered.session.refresh_token == "signed-session-1"
        assert registered.session.expires_in == 900

        refreshed = await service.refresh("signed-session-1")
        assert refreshed.session is not None
        assert refreshed.session.access_token == _access_jwt()
        assert refreshed.user["email"] == "a@example.com"

        await service.logout("signed-session-1")
    finally:
        await service.aclose()
        await client.aclose()

    sign_up = seen[0]
    assert sign_up["path"] == "/sign-up/email"
    assert sign_up["origin"] == "http://localhost:5173"
    assert sign_up["body"]["password"] == "Password1"
    assert sign_up["body"]["name"] == "A"
    assert seen[1]["path"] == "/token" and seen[1]["method"] == "GET"
    assert seen[2]["path"] == "/token" and seen[2]["method"] == "GET"
    assert seen[2]["cookie"] == f"{SESSION_COOKIE}=signed-session-1"
    assert seen[-1]["path"] == "/sign-out"
    assert seen[-1]["cookie"] == f"{SESSION_COOKIE}=signed-session-1"


@pytest.mark.asyncio
async def test_neon_auth_error_mapping(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sign-up/email":
            return httpx.Response(400, json={"message": "User already registered"})
        return httpx.Response(
            401, json={"message": "Invalid email or password", "code": "INVALID_EMAIL_OR_PASSWORD"}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = NeonAuthService(_settings(tmp_path), client=client)
    try:
        with pytest.raises(ConflictError):
            await service.register(
                email="a@example.com", password="Password1", full_name="A"
            )
        with pytest.raises(AuthenticationError, match="Invalid email or password"):
            await service.login(email="a@example.com", password="wrong")
    finally:
        await service.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_neon_auth_refresh_rejects_invalid_session(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = NeonAuthService(_settings(tmp_path), client=client)
    try:
        with pytest.raises(AuthenticationError, match="session is invalid"):
            await service.refresh("expired-session-token")
    finally:
        await service.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_neon_auth_rate_limit_maps_to_rate_limit_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"message": "Too many requests"}, headers={"Retry-After": "7"}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = NeonAuthService(_settings(tmp_path), client=client)
    try:
        with pytest.raises(RateLimitError, match="rate limit"):
            await service.login(email="a@example.com", password="Password1")
    finally:
        await service.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_neon_auth_google_authorization(tmp_path):
    seen: list[dict] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(_auth_handler(seen)))
    service = NeonAuthService(_settings(tmp_path), client=client)
    try:
        result = await service.google_authorization(
            redirect_to="http://localhost:5173/auth/callback"
        )
    finally:
        await service.aclose()
        await client.aclose()
    assert result["authorization_url"] == f"{AUTH_BASE}/callback/google"
    assert result["redirect_to"] == "http://localhost:5173/auth/callback"
    social = next(c for c in seen if c["path"] == "/sign-in/social")
    assert social["body"]["provider"] == "google"
    assert social["body"]["callbackURL"] == "http://localhost:5173/auth/callback"


@pytest.mark.asyncio
async def test_neon_auth_unconfigured_is_service_unavailable(tmp_path):
    service = NeonAuthService(_settings(tmp_path, neon_auth_base_url=None))
    try:
        with pytest.raises(ServiceUnavailableError, match="NEON_AUTH_BASE_URL"):
            await service.register(
                email="a@example.com", password="Password1", full_name="A"
            )
        with pytest.raises(ServiceUnavailableError, match="NEON_AUTH_BASE_URL"):
            await service.google_authorization(
                redirect_to="http://localhost:5173/auth/callback"
            )
    finally:
        await service.aclose()


def _valid_ai_plan() -> AIItinerary:
    return AIItinerary(
        title="Test plan",
        summary="A test.",
        days=[
            AIDay(
                day_number=1,
                date=date.today() + timedelta(days=1),
                title="Day one",
                activities=[
                    AIActivity(
                        place_id="attr_1",
                        start_time="09:00",
                        end_time="10:00",
                        description="Test activity",
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_gemini_structured_output_and_json_fallback(tmp_path):
    plan = _valid_ai_plan()

    class FakeModels:
        def __init__(self, response):
            self.response = response

        async def generate_content(self, **kwargs):
            assert kwargs["config"].response_mime_type == "application/json"
            return self.response

    class FakeAio:
        def __init__(self, response):
            self.models = FakeModels(response)

    class FakeClient:
        def __init__(self, response):
            self.aio = FakeAio(response)

    parsed_service = GeminiService(
        _settings(tmp_path), client=FakeClient(SimpleNamespace(parsed=plan))
    )
    try:
        assert (await parsed_service.generate_itinerary("prompt")).title == "Test plan"
    finally:
        await parsed_service.aclose()

    dict_service = GeminiService(
        _settings(tmp_path), client=FakeClient(SimpleNamespace(parsed=plan.model_dump()))
    )
    try:
        assert (await dict_service.generate_itinerary("prompt")).title == "Test plan"
    finally:
        await dict_service.aclose()

    json_service = GeminiService(
        _settings(tmp_path),
        client=FakeClient(
            SimpleNamespace(
                parsed=None,
                text=f"```json\n{json.dumps(plan.model_dump(mode='json'))}\n```",
            )
        ),
    )
    try:
        assert (await json_service.generate_itinerary("prompt")).title == "Test plan"
    finally:
        await json_service.aclose()


@pytest.mark.asyncio
async def test_gemini_rejects_invalid_output(tmp_path):
    class FakeModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=None, text="not json")

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        aio = FakeAio()

    service = GeminiService(_settings(tmp_path), client=FakeClient())
    try:
        with pytest.raises(AIGenerationError):
            await service.generate_itinerary("prompt")
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_gemini_unconfigured(tmp_path):
    service = GeminiService(_settings(tmp_path, gemini_api_key=None))
    try:
        with pytest.raises(ServiceUnavailableError):
            await service.generate_itinerary("prompt")
    finally:
        await service.aclose()
