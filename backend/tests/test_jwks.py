"""Neon Auth JWT verification tests (EdDSA JWKS, mirroring Managed Better Auth)."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import SecretStr

from app.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    ServiceUnavailableError,
)
from app.core.security import NeonTokenVerifier

AUTH_BASE = "https://auth-host.neonauth.region.aws.neon.tech"
JWKS_URL = f"{AUTH_BASE}/.well-known/jwks.json"


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "neon_auth_base_url": AUTH_BASE,
        "neon_auth_jwks_url": JWKS_URL,
        "neon_auth_jwks_cache_seconds": 3600,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _keypair_and_jwk():
    private_key = Ed25519PrivateKey.generate()
    raw_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    jwk = {
        "kty": "OKP",
        "crv": "Ed25519",
        "alg": "EdDSA",
        "kid": "test-kid",
        "x": base64.urlsafe_b64encode(raw_public).decode().rstrip("="),
    }
    return private_key, jwk


def _claims() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "sub": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "email": "traveler@example.com",
        "emailVerified": False,
        "name": "JWKS Traveler",
        "role": "authenticated",
        "aud": AUTH_BASE,
        "iss": AUTH_BASE,
        "iat": now.timestamp(),
        "exp": now.timestamp() + 900,
    }


def _token(private_key, *, kid: str | None = "test-kid", claims=None) -> str:
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(
        claims or _claims(),
        private_key,
        algorithm="EdDSA",
        headers=headers,
    )


@pytest.mark.asyncio
async def test_eddsa_token_is_verified_through_jwks_and_cached():
    private_key, jwk = _keypair_and_jwk()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert str(request.url) == JWKS_URL
        return httpx.Response(200, json={"keys": [jwk]})

    claims = _claims()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        first = await verifier.verify(_token(private_key, claims=claims))
        assert first.email == "traveler@example.com"
        assert first.full_name == "JWKS Traveler"
        assert first.role == "authenticated"
        second = await verifier.verify(_token(private_key, claims=claims))
        assert second.user_id == first.user_id
        assert calls == 1


@pytest.mark.asyncio
async def test_unknown_kid_triggers_refresh_then_fails():
    private_key, jwk = _keypair_and_jwk()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"keys": [jwk]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        await verifier.verify(_token(private_key))
        with pytest.raises(AuthenticationError, match="unknown signing key"):
            await verifier.verify(_token(private_key, kid="rotated-away"))
        assert calls == 2


@pytest.mark.asyncio
async def test_algorithm_confusion_is_rejected():
    private_key, jwk = _keypair_and_jwk()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    claims = _claims()
    claims["alg_override"] = None  # placeholder; header forgery tested below
    # Sign the same claims with HS256 but keep the JWKS-provided kid so the
    # verifier must reject a token whose algorithm differs from the key's.
    hs_token = jwt.encode(
        _claims(),
        "symmetric-secret-that-is-long-enough-for-hs256-tests",
        algorithm="HS256",
        headers={"kid": "test-kid"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        with pytest.raises(AuthenticationError, match="does not match its signing key"):
            await verifier.verify(hs_token)
    assert private_key is not None


@pytest.mark.asyncio
async def test_jwks_transport_and_payload_failures_are_sanitised():
    private_key, _ = _keypair_and_jwk()

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(failing_handler)
    ) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        with pytest.raises(ExternalServiceError):
            await verifier.verify(_token(private_key))

    def malformed_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": "not-a-list"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(malformed_handler)
    ) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        with pytest.raises(ExternalServiceError, match="malformed JWKS"):
            await verifier.verify(_token(private_key))


@pytest.mark.asyncio
async def test_missing_kid_and_unsupported_algorithm_are_rejected():
    private_key, jwk = _keypair_and_jwk()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        with pytest.raises(AuthenticationError, match="signing key id"):
            await verifier.verify(_token(private_key, kid=None))

    unsupported = jwt.encode(
        _claims(),
        "not-a-real-secret-but-long-enough-for-hs384-signing-and-tests",
        algorithm="HS384",
    )
    with pytest.raises(AuthenticationError, match="Unsupported"):
        await NeonTokenVerifier(_settings()).verify(unsupported)


@pytest.mark.asyncio
async def test_expired_and_wrong_issuer_tokens_are_rejected():
    private_key, jwk = _keypair_and_jwk()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    now = datetime.now(timezone.utc)
    expired = _claims()
    expired["iat"] = now.timestamp() - 3600
    expired["exp"] = now.timestamp() - 1800
    wrong_issuer = _claims()
    wrong_issuer["iss"] = "https://evil.example.com"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        with pytest.raises(AuthenticationError, match="expired"):
            await verifier.verify(_token(private_key, claims=expired))
        with pytest.raises(AuthenticationError, match="issuer is invalid"):
            await verifier.verify(_token(private_key, claims=wrong_issuer))


@pytest.mark.asyncio
async def test_missing_role_is_rejected():
    private_key, jwk = _keypair_and_jwk()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [jwk]})

    claims = _claims()
    claims.pop("role")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verifier = NeonTokenVerifier(_settings(), client=client)
        with pytest.raises(AuthenticationError, match="authenticated"):
            await verifier.verify(_token(private_key, claims=claims))


@pytest.mark.asyncio
async def test_hs256_requires_explicitly_configured_secret():
    claims = _claims()
    token = jwt.encode(claims, "test-secret-that-is-long-enough-for-hs256", algorithm="HS256")
    with pytest.raises(ServiceUnavailableError, match="AUTH_HS256_SECRET"):
        await NeonTokenVerifier(_settings()).verify(token)

    settings = _settings(auth_hs256_secret=SecretStr("test-secret-that-is-long-enough-for-hs256"))
    user = await NeonTokenVerifier(settings).verify(token)
    assert user.email == "traveler@example.com"
