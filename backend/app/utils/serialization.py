"""Helpers for normalising values returned by PostgreSQL and SQLite."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def loads_json(value: Any, default: Any) -> Any:
    """Decode a JSON column regardless of driver (JSONB dict or SQLite text)."""

    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def normalise_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def normalise_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: normalise_value(value) for key, value in dict(row).items()}


def normalise_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalise_row(row) for row in rows]  # type: ignore[misc]
