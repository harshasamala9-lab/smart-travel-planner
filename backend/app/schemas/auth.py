"""Authentication request/response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import ResponseModel, StrictModel
from app.schemas.users import ProfileResponse


class RegisterRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        if not any(char.isalpha() for char in value) or not any(
            char.isdigit() for char in value
        ):
            raise ValueError("Password must include at least one letter and one number")
        return value


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(StrictModel):
    # The Neon Auth session token (7-day lifetime) returned by register/login.
    refresh_token: str = Field(min_length=10)


class LogoutRequest(StrictModel):
    # The Neon Auth session token to revoke. An already-issued access JWT
    # stays valid until its own expiry (at most 15 minutes).
    refresh_token: str = Field(min_length=10)


class SessionResponse(ResponseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    expires_at: int | None = None


class UserIdentity(ResponseModel):
    id: UUID
    email: str | None = None
    email_confirmed: bool = False
    provider: str = "email"
    full_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime | None = None


class AuthResponse(ResponseModel):
    user: UserIdentity
    session: SessionResponse | None = None
    profile: ProfileResponse
    email_confirmation_required: bool = False


class TokenResponse(ResponseModel):
    session: SessionResponse
    user: UserIdentity
    profile: ProfileResponse


class GoogleAuthorizeResponse(ResponseModel):
    authorization_url: str
    provider: str = "google"
    redirect_to: str
