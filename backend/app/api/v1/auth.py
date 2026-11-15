"""Neon Auth endpoints, including Google social OAuth via Managed Better Auth."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.config import Settings
from app.core.exceptions import ValidationAppError
from app.dependencies import (
    get_auth_service,
    get_profile_repository,
    get_settings,
)
from app.database.repositories import ProfileRepository
from app.schemas.auth import (
    AuthResponse,
    GoogleAuthorizeResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
    UserIdentity,
)
from app.schemas.common import MessageResponse
from app.services.neon_auth_service import AuthResult, NeonAuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _identity(result: AuthResult) -> UserIdentity:
    user = result.user
    return UserIdentity(
        id=user["id"],
        email=user.get("email"),
        email_confirmed=bool(user.get("email_confirmed")),
        provider=str(user.get("provider") or "email"),
        full_name=user.get("full_name"),
        avatar_url=user.get("avatar_url"),
        created_at=user.get("created_at"),
    )


async def _ensure_profile(
    profiles: ProfileRepository,
    result: AuthResult,
    *,
    fallback_name: str | None = None,
) -> dict:
    user = result.user
    return await profiles.ensure_from_auth(
        user_id=user["id"],
        email=user.get("email") or f"{user['id']}@no-email.invalid",
        full_name=user.get("full_name") or fallback_name,
        avatar_url=user.get("avatar_url"),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register with email and password",
    responses={
        409: {"description": "An account with this email already exists"},
        422: {"description": "Validation error"},
        502: {"description": "Neon Auth unavailable"},
    },
)
async def register(
    payload: RegisterRequest,
    auth: Annotated[NeonAuthService, Depends(get_auth_service)],
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> AuthResponse:
    result = await auth.register(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
    )
    profile = await _ensure_profile(profiles, result, fallback_name=payload.full_name)
    return AuthResponse(
        user=_identity(result),
        session=SessionResponse(**result.session.as_dict()) if result.session else None,
        profile=profile,
        email_confirmation_required=result.session is None,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
    responses={401: {"description": "Invalid email or password"}},
)
async def login(
    payload: LoginRequest,
    auth: Annotated[NeonAuthService, Depends(get_auth_service)],
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> AuthResponse:
    result = await auth.login(email=str(payload.email), password=payload.password)
    profile = await _ensure_profile(profiles, result)
    return AuthResponse(
        user=_identity(result),
        session=SessionResponse(**result.session.as_dict()) if result.session else None,
        profile=profile,
        email_confirmation_required=False,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh the access token with a session token",
    description=(
        "Exchanges the 7-day session token (the refresh_token returned by "
        "register/login) for a fresh 15-minute EdDSA access JWT. The session "
        "token itself does not rotate."
    ),
    responses={401: {"description": "Invalid or expired session token"}},
)
async def refresh_token(
    payload: RefreshRequest,
    auth: Annotated[NeonAuthService, Depends(get_auth_service)],
    profiles: Annotated[ProfileRepository, Depends(get_profile_repository)],
) -> TokenResponse:
    result = await auth.refresh(payload.refresh_token)
    if result.session is None:
        raise ValidationAppError("Neon Auth did not return a refreshed session.")
    profile = await _ensure_profile(profiles, result)
    return TokenResponse(
        session=SessionResponse(**result.session.as_dict()),
        user=_identity(result),
        profile=profile,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke the Neon Auth session",
    description=(
        "Revokes the session identified by the session token (the refresh_token "
        "value returned by register/login). An access JWT that was already "
        "issued stays valid until its own expiry (at most 15 minutes)."
    ),
    responses={401: {"description": "Invalid or expired session token"}},
)
async def logout(
    payload: LogoutRequest,
    auth: Annotated[NeonAuthService, Depends(get_auth_service)],
) -> MessageResponse:
    await auth.logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.get(
    "/google/url",
    response_model=GoogleAuthorizeResponse,
    summary="Create a Google OAuth authorization URL",
    description=(
        "Starts Google sign-in through Managed Better Auth. Open the returned "
        "authorization_url in a browser; Neon Auth completes the OAuth exchange "
        "at its own callback and redirects the user to redirect_to (which must "
        "be a trusted domain registered with `neon neon-auth domain add`)."
    ),
    responses={503: {"description": "Neon Auth is not configured"}},
)
async def google_authorization_url(
    settings: Annotated[Settings, Depends(get_settings)],
    auth: Annotated[NeonAuthService, Depends(get_auth_service)],
    redirect_to: Annotated[
        str | None,
        Query(
            description=(
                "Exact redirect URL registered as a Neon Auth trusted domain; "
                "must be in the allowed list."
            ),
            max_length=500,
        ),
    ] = None,
) -> GoogleAuthorizeResponse:
    target = (redirect_to or settings.google_oauth_redirect_url).rstrip("/")
    if target not in settings.oauth_allowed_redirects:
        raise ValidationAppError(
            "redirect_to is not an allowed frontend URL.",
            details={"allowed_redirects": sorted(settings.oauth_allowed_redirects)},
        )
    result = await auth.google_authorization(redirect_to=target)
    return GoogleAuthorizeResponse(**result)
