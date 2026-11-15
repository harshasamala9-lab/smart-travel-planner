"""Shared API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject unknown request fields to catch client typos early."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class MessageResponse(BaseModel):
    message: str


class HealthCheck(BaseModel):
    status: str
    dialect: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    checks: dict[str, Any]
