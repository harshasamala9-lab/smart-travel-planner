"""Authentication primitives: Neon Auth JWT verification.

Neon Auth (Managed Better Auth) owns password storage and identity. This
backend never receives or stores a password database. Access tokens are EdDSA
JWTs (Ed25519, 15-minute expiry, ``iss``/``aud`` equal to the Auth base URL)
verified locally against the branch JWKS before any protected endpoint is
served. An HS256 path exists only for offline tests and local development.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK

from app.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    ServiceUnavailableError,
)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Identity extracted from a verified Neon Auth access token."""

    user_id: uuid.UUID
    email: str
    role: str
    claims: dict[str, Any]

    @property
    def full_name(self) -> str | None:
        name = self.claims.get("name")
        return str(name).strip() if name else None

    @property
    def avatar_url(self) -> str | None:
        avatar = self.claims.get("image") or self.claims.get("picture")
        return str(avatar).strip() if avatar else None

    @property
    def provider(self) -> str:
        return str(self.claims.get("provider") or "email")


class JWKSKeyStore:
    """Small TTL cache for Neon Auth's asymmetric signing keys."""

    def __init__(
        self,
        jwks_url: str,
        *,
        ttl_seconds: int,
        client: httpx.AsyncClient,
    ) -> None:
        self._jwks_url = jwks_url
        self._ttl_seconds = ttl_seconds
        self._client = client
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = 0.0

    async def get_key(self, kid: str, algorithm: str) -> PyJWK:
        now = time.monotonic()
        key = self._keys.get(kid)
        if key is not None and now < self._expires_at:
            return key

        await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise AuthenticationError("The authentication token uses an unknown signing key.")
        # Never let a token choose an algorithm that differs from the one
        # advertised for the selected JWKS key. This prevents algorithm
        # confusion between asymmetric and HMAC families.
        if key.algorithm_name != algorithm:
            raise AuthenticationError(
                "The authentication token algorithm does not match its signing key."
            )
        return key

    async def _refresh(self) -> None:
        try:
            response = await self._client.get(self._jwks_url, timeout=10.0)
        except httpx.TimeoutException as exc:
            raise ExternalServiceTimeoutError(
                "Could not retrieve Neon Auth signing keys in time."
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError(
                "Could not retrieve Neon Auth signing keys."
            ) from exc

        if response.status_code != 200:
            raise ExternalServiceError(
                "Neon Auth rejected the signing-key request.",
                details={"upstream_status": response.status_code},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError("Neon Auth returned malformed JWKS data.") from exc

        raw_keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(raw_keys, list):
            raise ExternalServiceError("Neon Auth returned malformed JWKS data.")

        keys: dict[str, PyJWK] = {}
        for jwk_data in raw_keys:
            if not isinstance(jwk_data, dict) or not jwk_data.get("kid"):
                continue
            try:
                keys[str(jwk_data["kid"])] = PyJWK.from_dict(jwk_data)
            except Exception:  # pragma: no cover - ignore unsupported keys
                continue
        if not keys:
            raise ExternalServiceError("Neon Auth returned no usable signing keys.")
        self._keys = keys
        self._expires_at = time.monotonic() + self._ttl_seconds


class NeonTokenVerifier:
    """Verify Neon Auth access tokens securely.

    Production tokens are EdDSA (Ed25519) JWTs whose signing keys are fetched
    from the branch JWKS endpoint and cached. HS256 verification is available
    only when ``AUTH_HS256_SECRET`` is configured, which is reserved for
    offline tests and local development (production settings reject it).
    """

    _ASYMMETRIC_ALGORITHMS = {
        "RS256",
        "RS384",
        "RS512",
        "ES256",
        "ES384",
        "ES512",
        "PS256",
        "PS384",
        "PS512",
        "EdDSA",
    }

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._jwks: JWKSKeyStore | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": "smart-travel-planner-backend/1.0"},
            )
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _issuer(self) -> str | None:
        return self._settings.auth_issuer

    async def verify(self, token: str) -> AuthenticatedUser:
        if not token or token.count(".") != 2:
            raise AuthenticationError("Malformed bearer token.")

        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise AuthenticationError("Malformed bearer token.") from exc

        algorithm = str(header.get("alg", ""))
        if not algorithm:
            raise AuthenticationError("Bearer token is missing its signing algorithm.")

        issuer = self._issuer()
        options: dict[str, Any] = {
            "require": ["exp", "sub"],
            "verify_exp": True,
            "verify_aud": issuer is not None,
            "verify_iss": issuer is not None,
        }
        kwargs: dict[str, Any] = {
            "algorithms": [algorithm],
            "audience": issuer,
            "issuer": issuer,
            "leeway": self._settings.jwt_leeway_seconds,
            "options": options,
        }

        if algorithm == "HS256":
            # Neon Auth signs access tokens with EdDSA and references signing
            # keys via kid in the JWKS. An HS256 token claiming a JWKS kid is
            # an algorithm-confusion attempt and is always rejected.
            if header.get("kid"):
                raise AuthenticationError(
                    "Bearer token algorithm does not match its signing key."
                )
            secret = self._settings.auth_hs256_key
            if not secret:
                raise ServiceUnavailableError(
                    "AUTH_HS256_SECRET is not configured for HS256 token verification."
                )
            key: Any = secret
        elif algorithm in self._ASYMMETRIC_ALGORITHMS:
            jwks_url = self._settings.neon_auth_jwks_url
            if not jwks_url:
                raise ServiceUnavailableError(
                    "NEON_AUTH_JWKS_URL is required to verify asymmetric Neon Auth tokens."
                )
            if self._jwks is None:
                self._jwks = JWKSKeyStore(
                    jwks_url,
                    ttl_seconds=self._settings.neon_auth_jwks_cache_seconds,
                    client=await self._get_client(),
                )
            kid = str(header.get("kid") or "")
            if not kid:
                raise AuthenticationError("Bearer token is missing its signing key id.")
            key = (await self._jwks.get_key(kid, algorithm)).key
        else:
            raise AuthenticationError("Unsupported bearer token algorithm.")

        try:
            claims = jwt.decode(token, key, **kwargs)
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("The authentication token has expired.") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationError("The authentication token audience is invalid.") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError("The authentication token issuer is invalid.") from exc
        except InvalidTokenError as exc:
            raise AuthenticationError("The authentication token is invalid.") from exc

        role = str(claims.get("role") or "")
        if role != "authenticated":
            raise AuthenticationError("Only authenticated user tokens are accepted.")

        subject = str(claims.get("sub") or "")
        try:
            user_id = uuid.UUID(subject)
        except ValueError as exc:
            raise AuthenticationError("The authentication token subject is invalid.") from exc

        email = str(claims.get("email") or "")
        return AuthenticatedUser(
            user_id=user_id,
            email=email,
            role=role,
            claims=claims,
        )
