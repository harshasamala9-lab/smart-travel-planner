"""Cross-cutting HTTP security, rate limiting, timeouts, and logging."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections import defaultdict, deque
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import ClientDisconnect

from app.config import Settings

logger = logging.getLogger("smart_travel.api")
access_logger = logging.getLogger("smart_travel.access")

_SHARE_TOKEN_PATH = re.compile(r"(/shared/itineraries/)[^/]+")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _redact_path(path: str) -> str:
    """Do not write share-link bearer tokens to application access logs."""
    return _SHARE_TOKEN_PATH.sub(r"\1[redacted]", path)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": None,
                "request_id": request_id,
            }
        },
        headers=headers,
    )


def install_middlewares(app: FastAPI, settings: Settings) -> None:
    auth_paths = {
        f"{settings.api_v1_prefix}/auth/register",
        f"{settings.api_v1_prefix}/auth/login",
        f"{settings.api_v1_prefix}/auth/refresh",
        f"{settings.api_v1_prefix}/auth/google/url",
    }
    rate_windows: dict[str, deque[float]] = defaultdict(deque)
    rate_lock = asyncio.Lock()

    @app.middleware("http")
    async def security_and_observability(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied_request_id = request.headers.get("X-Request-ID") or ""
        request_id = (
            supplied_request_id
            if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        started = time.perf_counter()
        deadline = started + settings.request_timeout_seconds

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_body_bytes:
                    response: Response = _error_response(
                        413,
                        "payload_too_large",
                        "The request body is too large.",
                        request_id,
                    )
                    return _apply_headers(response, request_id, settings, request.url.path)
            except ValueError:
                response = _error_response(
                    400,
                    "invalid_content_length",
                    "Invalid Content-Length header.",
                    request_id,
                )
                return _apply_headers(response, request_id, settings, request.url.path)

        # Content-Length is advisory and can be omitted for chunked requests.
        # Buffer the body up to the configured limit so an oversized chunked
        # upload cannot bypass the check or exhaust memory. The cached body is
        # replayed by Starlette's BaseHTTPMiddleware to the downstream app.
        body = bytearray()
        try:
            async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
                async for chunk in request.stream():
                    if len(body) + len(chunk) > settings.max_request_body_bytes:
                        response = _error_response(
                            413,
                            "payload_too_large",
                            "The request body is too large.",
                            request_id,
                        )
                        return _apply_headers(
                            response, request_id, settings, request.url.path
                        )
                    body.extend(chunk)
        except TimeoutError:
            response = _error_response(
                504,
                "request_timeout",
                "The request exceeded the server time limit.",
                request_id,
            )
            return _apply_headers(response, request_id, settings, request.url.path)
        except ClientDisconnect:
            response = _error_response(
                400,
                "client_disconnected",
                "The client disconnected before the request body was complete.",
                request_id,
            )
            return _apply_headers(response, request_id, settings, request.url.path)
        request._body = bytes(body)  # type: ignore[attr-defined]

        if request.url.path in auth_paths:
            client_host = request.client.host if request.client else "unknown"
            key = f"{client_host}:{request.url.path}"
            now = time.monotonic()
            async with rate_lock:
                window = rate_windows[key]
                while window and window[0] <= now - settings.auth_rate_limit_window_seconds:
                    window.popleft()
                if len(window) >= settings.auth_rate_limit_requests:
                    retry_after = max(
                        1,
                        int(
                            settings.auth_rate_limit_window_seconds
                            - (now - window[0])
                        ),
                    )
                    response = _error_response(
                        429,
                        "rate_limit_exceeded",
                        "Too many authentication attempts. Please try again later.",
                        request_id,
                        headers={"Retry-After": str(retry_after)},
                    )
                    return _apply_headers(response, request_id, settings, request.url.path)
                window.append(now)

        try:
            async with asyncio.timeout(max(0.001, deadline - time.monotonic())):
                response = await call_next(request)
        except TimeoutError:
            response = _error_response(
                504,
                "request_timeout",
                "The request exceeded the server time limit.",
                request_id,
            )

        duration_ms = (time.perf_counter() - started) * 1000
        access_logger.info(
            "%s %s %s %.1fms request_id=%s",
            request.method,
            _redact_path(request.url.path),
            response.status_code,
            duration_ms,
            request_id,
        )
        return _apply_headers(response, request_id, settings, request.url.path)

    if settings.allowed_host_list:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_host_list,
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )


def _apply_headers(
    response: Response,
    request_id: str,
    settings: Settings,
    path: str,
) -> Response:
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    if settings.app_env == "production":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if path.startswith(settings.api_v1_prefix) and not path.endswith("/photo"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path.startswith("/assets/"):
        response.headers.setdefault(
            "Cache-Control", "public, max-age=31536000, immutable"
        )
    elif not path.startswith(("/health", "/docs", "/redoc", "/openapi.json")):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response
