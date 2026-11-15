"""Health, middleware, error-envelope, and JWT verification tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.requests import Request

from app.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import NeonTokenVerifier
from app.main import create_app

from .conftest import TEST_AUTH_BASE_URL, TEST_JWT_SECRET


def test_health_and_index(client):
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["checks"]["database_dialect"] == "sqlite"

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"]["status"] == "up"

    index = client.get("/")
    assert index.status_code == 200
    # When a built SPA exists the root serves the app shell; otherwise the
    # API returns its JSON index. Both are valid deployment modes.
    if index.headers["content-type"].startswith("application/json"):
        assert index.json()["docs"] == "/docs"
    else:
        assert 'id="root"' in index.text


def test_openapi_documents_all_core_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/api/v1/auth/register",
        "/api/v1/auth/google/url",
        "/api/v1/users/me",
        "/api/v1/destinations/search",
        "/api/v1/itineraries/generate",
        "/api/v1/recommendations/",
        "/api/v1/weather/{destination}",
    ):
        assert expected in paths


def test_security_headers_and_request_id(client):
    response = client.get("/health", headers={"X-Request-ID": "caller-request-id"})
    assert response.headers["X-Request-ID"] == "caller-request-id"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"

    unsafe = client.get(
        "/health", headers={"X-Request-ID": "contains spaces and <script>"}
    )
    assert unsafe.headers["X-Request-ID"] != "contains spaces and <script>"
    assert len(unsafe.headers["X-Request-ID"]) == 32


def test_authentication_error_envelope(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "authentication_required"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_malformed_bearer_token_rejected(client):
    response = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_validation_errors_do_not_echo_passwords(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "zzz7", "full_name": ""},
    )
    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "validation_error"
    serialized = str(payload)
    assert "zzz7" not in serialized
    assert "'input'" not in serialized


def test_cors_preflight(client):
    response = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.asyncio
async def test_token_verifier_accepts_valid_hs256(settings, token):
    verifier = NeonTokenVerifier(settings)
    try:
        user = await verifier.verify(token)
    finally:
        await verifier.aclose()
    assert user.email == "traveler@example.com"
    assert user.role == "authenticated"
    assert user.full_name == "Test Traveler"


@pytest.mark.asyncio
async def test_token_verifier_rejects_expired_token(settings, user_id):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "traveler@example.com",
            "role": "authenticated",
            "aud": TEST_AUTH_BASE_URL,
            "iss": TEST_AUTH_BASE_URL,
            "iat": now.timestamp() - 3600,
            "exp": now.timestamp() - 1800,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    verifier = NeonTokenVerifier(settings)
    try:
        with pytest.raises(AuthenticationError, match="expired"):
            await verifier.verify(token)
    finally:
        await verifier.aclose()


@pytest.mark.asyncio
async def test_token_verifier_rejects_wrong_audience(settings, user_id):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "traveler@example.com",
            "role": "authenticated",
            "aud": "https://other-branch.neonauth.region.aws.neon.tech",
            "iss": TEST_AUTH_BASE_URL,
            "iat": now.timestamp(),
            "exp": now.timestamp() + 900,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    verifier = NeonTokenVerifier(settings)
    try:
        with pytest.raises(AuthenticationError):
            await verifier.verify(token)
    finally:
        await verifier.aclose()


@pytest.mark.asyncio
async def test_token_verifier_rejects_non_authenticated_role(settings, user_id):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": "traveler@example.com",
            "role": "service_role",
            "aud": TEST_AUTH_BASE_URL,
            "iss": TEST_AUTH_BASE_URL,
            "iat": now.timestamp(),
            "exp": now.timestamp() + 900,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    verifier = NeonTokenVerifier(settings)
    try:
        with pytest.raises(AuthenticationError, match="Only authenticated"):
            await verifier.verify(token)
    finally:
        await verifier.aclose()


def test_rate_limit_returns_429(tmp_path):
    limited = Settings(
        app_env="test",
        database_url=SecretStr(f"sqlite:///{tmp_path / 'rate.db'}"),
        auto_create_schema=True,
        auth_rate_limit_requests=1,
        auth_rate_limit_window_seconds=60,
        allowed_hosts="testserver",
    )
    application = create_app(limited)
    with TestClient(application) as test_client:
        first = test_client.post("/api/v1/auth/login", json={})
        second = test_client.post("/api/v1/auth/login", json={})
    assert first.status_code == 422
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_request_body_limit(tmp_path):
    limited = Settings(
        app_env="test",
        database_url=SecretStr(f"sqlite:///{tmp_path / 'body.db'}"),
        auto_create_schema=True,
        max_request_body_bytes=1024,
        allowed_hosts="testserver",
    )
    application = create_app(limited)
    with TestClient(application) as test_client:
        response = test_client.post(
            "/api/v1/auth/login",
            content=b"x" * 4096,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_chunked_request_body_limit(tmp_path):
    limited = Settings(
        app_env="test",
        database_url=SecretStr(f"sqlite:///{tmp_path / 'chunked.db'}"),
        auto_create_schema=True,
        max_request_body_bytes=1024,
        allowed_hosts="testserver",
    )

    def oversized_chunks():
        yield b"x" * 800
        yield b"x" * 800

    application = create_app(limited)
    with TestClient(application) as test_client:
        response = test_client.post(
            "/api/v1/auth/login",
            content=oversized_chunks(),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_trusted_host_rejection(tmp_path):
    limited = Settings(
        app_env="test",
        database_url=SecretStr(f"sqlite:///{tmp_path / 'host.db'}"),
        auto_create_schema=True,
        allowed_hosts="api.example.com",
    )
    application = create_app(limited)
    with TestClient(application) as test_client:
        response = test_client.get("/health", headers={"Host": "evil.example.com"})
    assert response.status_code == 400
