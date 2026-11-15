"""Typed application exceptions translated to consistent JSON errors."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected application failures."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        self.headers = headers or {}
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "The request could not be processed."


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"
    message = "Valid authentication credentials are required."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
            headers={"WWW-Authenticate": "Bearer", **(headers or {})},
        )


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "The resource conflicts with an existing resource."


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
    message = "The provided data is invalid."


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"
    message = "Too many requests. Please try again later."

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after: int = 60,
        details: Any = None,
    ) -> None:
        super().__init__(
            message,
            details=details,
            headers={"Retry-After": str(retry_after)},
        )


class ExternalServiceError(AppError):
    """A third-party API failed or rejected the request."""

    status_code = 502
    code = "external_service_error"
    message = "An upstream travel service failed."


class ExternalServiceTimeoutError(ExternalServiceError):
    status_code = 504
    code = "external_service_timeout"
    message = "An upstream travel service timed out."


class AIGenerationError(ExternalServiceError):
    """The model responded, but its output could not be trusted/validated."""

    status_code = 502
    code = "ai_invalid_output"
    message = "The AI service returned an unusable itinerary. Please retry."


class ServiceUnavailableError(AppError):
    """The required integration is not configured in this environment."""

    status_code = 503
    code = "service_unavailable"
    message = "The requested integration is not configured."


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"
    message = "The database is temporarily unavailable."
