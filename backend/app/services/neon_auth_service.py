"""Neon Auth integration (Managed Better Auth): email/password and social OAuth.

Passwords are sent directly to the branch's Managed Better Auth server over TLS
and are never persisted, hashed, or logged by this backend.

Session model (verified against the branch's live Better Auth OpenAPI):

* ``POST /sign-up/email`` and ``POST /sign-in/email`` create a session and
  return the session token in the body plus ``__Secure-neon-auth.session_token``
  cookies. Sessions last 7 days.
* ``GET /token`` mints a short-lived (15-minute) EdDSA access JWT from the
  session cookie. That JWT is what API clients send as ``Authorization: Bearer``.
* ``POST /sign-out`` revokes the session. An already-issued JWT remains valid
  until its own expiry (at most 15 minutes).
* Server-to-server calls must carry a trusted ``Origin`` header; localhost
  ports are pre-approved and production origins are registered with
  ``neon neon-auth domain add``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt.exceptions import InvalidTokenError

from app.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationAppError,
)

logger = logging.getLogger(__name__)

SESSION_COOKIE = "__Secure-neon-auth.session_token"
DEFAULT_JWT_LIFETIME_SECONDS = 900


@dataclass(frozen=True, slots=True)
class AuthSession:
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_in: int | None
    expires_at: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: dict[str, Any]
    session: AuthSession | None


class NeonAuthService:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.neon_auth_timeout_seconds),
            headers={
                "Origin": settings.auth_origin,
                "Content-Type": "application/json",
            },
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.neon_auth_base_url)

    def _require_config(self) -> str:
        if not self._settings.neon_auth_base_url:
            raise ServiceUnavailableError(
                "Neon Auth is not configured. Set NEON_AUTH_BASE_URL (run "
                "`neon env pull` for the linked branch)."
            )
        return self._settings.neon_auth_base_url

    async def _request(
        self,
        method: str,
        path: str,
        *,
        action: str,
        json: dict[str, Any] | None = None,
        session_token: str | None = None,
    ) -> httpx.Response:
        self._require_config()
        url = f"{self._settings.neon_auth_base_url}{path}"
        headers: dict[str, str] = {"Origin": self._settings.auth_origin}
        if session_token:
            headers["Cookie"] = f"{SESSION_COOKIE}={session_token}"
        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                json=json,
                timeout=self._settings.neon_auth_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ExternalServiceTimeoutError(
                "Neon Auth did not respond in time."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "Neon Auth network failure during %s: %s", action, type(exc).__name__
            )
            raise ExternalServiceError("Neon Auth is currently unreachable.") from exc
        return response

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return ""
        if not isinstance(payload, dict):
            return ""
        for key in ("message", "error", "code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _raise_auth_error(self, response: httpx.Response, action: str) -> None:
        message = self._error_message(response)
        if response.status_code == 429:
            retry_after = 60
            try:
                retry_after = int(response.headers.get("Retry-After", "60"))
            except ValueError:
                pass
            raise RateLimitError(
                "Neon Auth rate limit reached. Please retry later.",
                retry_after=max(1, retry_after),
            )

        if action == "register":
            lowered = message.lower()
            if "already" in lowered and ("registered" in lowered or "exists" in lowered):
                raise ConflictError("An account with this email already exists.")
            if "user_already_exists" in lowered:
                raise ConflictError("An account with this email already exists.")
            if response.status_code in {400, 422}:
                raise ValidationAppError(
                    "Neon Auth rejected the registration details.",
                    details={"upstream_message": message[:300]},
                )
        if action in {"login", "refresh", "logout"} and response.status_code in {400, 401, 403}:
            raise AuthenticationError(
                "Invalid email or password."
                if action == "login"
                else "The session is invalid or has expired."
            )
        if response.status_code in {400, 401, 403}:
            raise AuthenticationError("Neon Auth rejected the request.")

        logger.warning(
            "Neon Auth %s failed with status %s", action, response.status_code
        )
        raise ExternalServiceError(
            "Neon Auth could not complete the request.",
            details={"upstream_status": response.status_code},
        )

    @staticmethod
    def _json_object(response: httpx.Response, action: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError(
                f"Neon Auth returned malformed JSON during {action}."
            ) from exc
        if not isinstance(payload, dict):
            raise ExternalServiceError("Neon Auth returned an unexpected payload.")
        return payload

    @staticmethod
    def _extract_user(payload: dict[str, Any]) -> dict[str, Any]:
        user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
        if not user.get("id"):
            raise ExternalServiceError("Neon Auth returned a user without an id.")
        return {
            "id": str(user["id"]),
            "email": user.get("email"),
            "email_confirmed": bool(user.get("emailVerified") or user.get("email_verified")),
            "provider": "email",
            "full_name": user.get("name"),
            "avatar_url": user.get("image") or user.get("picture"),
            "created_at": user.get("createdAt") or user.get("created_at"),
        }

    @staticmethod
    def _session_lifetime(jwt_token: str) -> int:
        try:
            claims = jwt.decode(jwt_token, options={"verify_signature": False})
        except InvalidTokenError:  # pragma: no cover - defensive
            return DEFAULT_JWT_LIFETIME_SECONDS
        expires_at = claims.get("exp")
        issued_at = claims.get("iat")
        if isinstance(expires_at, int) and isinstance(issued_at, int):
            return max(1, expires_at - issued_at)
        return DEFAULT_JWT_LIFETIME_SECONDS

    async def _mint_access_token(
        self, *, action: str, session_token: str | None = None
    ) -> AuthSession:
        """Exchange a session token (cookie value) for a fresh access JWT."""
        response = await self._request(
            "GET", "/token", action=action, session_token=session_token
        )
        if response.status_code != 200:
            self._raise_auth_error(response, "refresh")
        payload = self._json_object(response, action)
        access_token = payload.get("token")
        if not isinstance(access_token, str) or not access_token:
            raise ExternalServiceError("Neon Auth did not return an access token.")

        expires_in = self._session_lifetime(access_token)
        return AuthSession(
            access_token=access_token,
            refresh_token=session_token,
            token_type="bearer",
            expires_in=expires_in,
            expires_at=int(time.time()) + expires_in,
        )

    async def _session_from(
        self,
        response: httpx.Response,
        *,
        action: str,
    ) -> AuthResult:
        payload = self._json_object(response, action)
        user = self._extract_user(payload)
        # Better Auth signs its session cookie: the Set-Cookie value is
        # "<token>.<signature>" and is longer than the raw "token" in the
        # response body. Verified live: only the full signed value is accepted
        # by GET /token, GET /get-session, and POST /sign-out, so it is the
        # value we hand out as refresh_token. The shared client cookie jar is
        # never read back, so concurrent users of one client cannot leak
        # sessions into each other.
        session_token = response.cookies.get(SESSION_COOKIE) or payload.get("token")
        if not isinstance(session_token, str) or not session_token:
            # Email verification flows can withhold the session token.
            return AuthResult(user=user, session=None)
        session = await self._mint_access_token(
            action=action, session_token=session_token
        )
        return AuthResult(user=user, session=session)

    async def register(self, *, email: str, password: str, full_name: str) -> AuthResult:
        response = await self._request(
            "POST",
            "/sign-up/email",
            action="register",
            json={"email": email, "password": password, "name": full_name},
        )
        if response.status_code not in {200, 201}:
            self._raise_auth_error(response, "register")
        return await self._session_from(response, action="register")

    async def login(self, *, email: str, password: str) -> AuthResult:
        response = await self._request(
            "POST",
            "/sign-in/email",
            action="login",
            json={"email": email, "password": password},
        )
        if response.status_code not in {200, 201}:
            self._raise_auth_error(response, "login")
        return await self._session_from(response, action="login")

    async def refresh(self, session_token: str) -> AuthResult:
        """Mint a fresh access JWT from a valid session token.

        The session token itself does not rotate; it stays valid for 7 days
        from creation.
        """
        response = await self._request(
            "GET", "/token", action="refresh", session_token=session_token
        )
        if response.status_code != 200:
            self._raise_auth_error(response, "refresh")
        payload = self._json_object(response, "refresh")
        access_token = payload.get("token")
        if not isinstance(access_token, str) or not access_token:
            raise ExternalServiceError("Neon Auth did not return a refreshed token.")

        session = self._session_from_jwt(
            access_token, refresh_token=session_token
        )
        user = await self.describe_user(session_token)
        return AuthResult(user=user, session=session)

    @staticmethod
    def _session_from_jwt(access_token: str, *, refresh_token: str) -> AuthSession:
        expires_in = NeonAuthService._session_lifetime(access_token)
        return AuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            expires_at=int(time.time()) + expires_in,
        )

    async def describe_user(self, session_token: str) -> dict[str, Any]:
        """Return the current session's user via ``GET /get-session``."""
        response = await self._request(
            "GET", "/get-session", action="session", session_token=session_token
        )
        if response.status_code == 401:
            raise AuthenticationError("The session is invalid or has expired.")
        if response.status_code != 200:
            self._raise_auth_error(response, "session")
        payload = self._json_object(response, "session")
        user_payload = payload.get("user")
        if not isinstance(user_payload, dict) or not user_payload.get("id"):
            raise AuthenticationError("The session is invalid or has expired.")
        user = self._extract_user(payload)
        user["provider"] = "email"
        return user

    async def logout(self, session_token: str) -> None:
        response = await self._request(
            "POST", "/sign-out", action="logout", json={}, session_token=session_token
        )
        if response.status_code not in {200, 204, 401}:
            self._raise_auth_error(response, "logout")

    async def google_authorization(self, *, redirect_to: str) -> dict[str, str]:
        """Start Google sign-in through Managed Better Auth social OAuth.

        Managed Auth performs the OAuth exchange itself; the returned URL is
        opened in a browser and the session is established at Neon Auth's
        callback, then the user is redirected to ``callbackURL``.
        """
        response = await self._request(
            "POST",
            "/sign-in/social",
            action="google",
            json={"provider": "google", "callbackURL": redirect_to},
        )
        if response.status_code != 200:
            self._raise_auth_error(response, "google")
        payload = self._json_object(response, "google")
        url = payload.get("url")
        if not isinstance(url, str) or not url:
            raise ExternalServiceError(
                "Neon Auth did not return a Google authorization URL."
            )
        return {
            "authorization_url": url,
            "redirect_to": redirect_to,
            "provider": "google",
        }
