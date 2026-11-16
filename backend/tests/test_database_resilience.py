"""Resilience tests for the Neon PostgreSQL connection layer.

Neon's transaction pooler silently closes idle TCP sockets and a cold compute
takes seconds to wake. The connection layer must absorb both (check + retry)
so users never see "database temporarily unavailable" errors.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

from app.core.exceptions import DatabaseUnavailableError
from app.database.connection import Database


class FakeCursor:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row
        self.rowcount = 1

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row

    async def fetchall(self) -> list[dict[str, Any]]:
        return [self._row] if self._row else []


class FakeConnection:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row

    def transaction(self) -> "FakeConnection":
        return self

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def execute(self, sql: str, params: Any = None) -> FakeCursor:
        return FakeCursor(self._row)


class _FailingCheckout:
    def __init__(self, error: BaseException) -> None:
        self._error = error

    async def __aenter__(self) -> Any:
        raise self._error

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _OkCheckout:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self._connection

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class FakePool:
    """Pool whose first ``failures`` checkouts fail with a stale socket."""

    def __init__(self, *, failures: int = 1, error: BaseException | None = None) -> None:
        self._failures = failures
        self._error = error or psycopg.OperationalError(
            "server closed the connection unexpectedly"
        )
        self.checkouts = 0

    def connection(self) -> Any:
        self.checkouts += 1
        if self.checkouts <= self._failures:
            return _FailingCheckout(self._error)
        return _OkCheckout(FakeConnection(row={"ok": 1}))


def postgres_database() -> Database:
    return Database("postgresql://user:pass@localhost:5432/travel")


@pytest.mark.asyncio
async def test_checkout_retries_once_on_stale_connection():
    db = postgres_database()
    db._pool = FakePool(failures=1)
    assert await db.execute("SELECT 1") == 1
    assert db._pool.checkouts == 2  # first attempt failed, retry succeeded


@pytest.mark.asyncio
async def test_checkout_failure_exhausts_retries_and_raises_unavailable():
    db = postgres_database()
    db._pool = FakePool(failures=5)
    with pytest.raises(DatabaseUnavailableError):
        await db.execute("SELECT 1")
    assert db._pool.checkouts == 2  # exactly CHECKOUT_RETRIES attempts


@pytest.mark.asyncio
async def test_operational_error_after_body_started_is_not_retried():
    """Work that already began must never be replayed (no duplicate effects)."""
    db = postgres_database()

    class MidBodyPool(FakePool):
        def connection(self) -> Any:
            self.checkouts += 1
            return _OkCheckout(FakeConnection())  # execute raises below

    pool = MidBodyPool()
    db._pool = pool

    from app.database.connection import PostgresTransaction

    original_execute = PostgresTransaction.execute

    async def failing_execute(self, sql, params=()):
        raise psycopg.OperationalError("connection lost mid-transaction")

    import app.database.connection as connection_module

    connection_module.PostgresTransaction.execute = failing_execute
    try:
        with pytest.raises(DatabaseUnavailableError):
            await db.execute("SELECT 1")
    finally:
        connection_module.PostgresTransaction.execute = original_execute
    assert pool.checkouts == 1  # no retry once the caller's body had started


@pytest.mark.asyncio
async def test_health_check_retries_then_reports_up():
    db = postgres_database()
    db._pool = FakePool(failures=1)
    health = await db.check_health()
    assert health == {"status": "up", "dialect": "postgresql"}


@pytest.mark.asyncio
async def test_health_check_raises_unavailable_after_retries():
    db = postgres_database()
    db._pool = FakePool(failures=5)
    with pytest.raises(DatabaseUnavailableError):
        await db.check_health()
    assert db._pool.checkouts == 2  # health check attempts


@pytest.mark.asyncio
async def test_connect_retries_with_backoff_then_recovers(monkeypatch):
    monkeypatch.setattr(Database, "CONNECT_BACKOFF_SECONDS", (0.0, 0.0, 0.0, 0.0))

    import psycopg_pool

    attempts: list[Any] = []

    class FlakyAsyncPool:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            attempts.append(self)

        @staticmethod
        def check_connection(conn: Any) -> bool:
            return True

        async def open(self, wait: bool = True, timeout: float | None = None) -> None:
            if len(attempts) < 3:
                raise OSError("temporary failure in name resolution")

        async def close(self, timeout: float | None = None) -> None:
            return None

    class FakeSyncPool:
        @staticmethod
        def check_connection(conn: Any) -> bool:
            return True

    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", FlakyAsyncPool)
    monkeypatch.setattr(psycopg_pool, "ConnectionPool", FakeSyncPool)

    async def healthy(self: Database) -> dict[str, str]:
        return {"status": "up", "dialect": "postgresql"}

    monkeypatch.setattr(Database, "check_health", healthy)

    db = postgres_database()
    await db.connect()
    assert len(attempts) == 3  # two transient failures, then success
    assert db._pool is attempts[-1]
    # Pool hardening settings must actually be passed through.
    kwargs = attempts[-1].kwargs
    assert kwargs["check"] == FlakyAsyncPool.check_connection
    assert kwargs["max_lifetime"] == 300.0
    assert kwargs["max_idle"] == db._pool_min_size
    assert "keepalives=1" in kwargs["conninfo"]


@pytest.mark.asyncio
async def test_connect_gives_up_after_four_attempts(monkeypatch):
    monkeypatch.setattr(Database, "CONNECT_BACKOFF_SECONDS", (0.0, 0.0, 0.0, 0.0))

    import psycopg_pool

    attempts: list[Any] = []

    class AlwaysBrokenPool:
        def __init__(self, **kwargs: Any) -> None:
            attempts.append(self)

        @staticmethod
        def check_connection(conn: Any) -> bool:
            return True

        async def open(self, wait: bool = True, timeout: float | None = None) -> None:
            raise OSError("network is unreachable")

        async def close(self, timeout: float | None = None) -> None:
            return None

    class FakeSyncPool:
        @staticmethod
        def check_connection(conn: Any) -> bool:
            return True

    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", AlwaysBrokenPool)
    monkeypatch.setattr(psycopg_pool, "ConnectionPool", FakeSyncPool)

    db = postgres_database()
    with pytest.raises(DatabaseUnavailableError):
        await db.connect()
    assert len(attempts) == Database.CONNECT_ATTEMPTS
    assert db._pool is None


def test_conninfo_includes_keepalives_and_connect_timeout():
    info = postgres_database()._postgresql_conninfo()
    assert "keepalives=1" in info
    assert "keepalives_idle=30" in info
    assert "connect_timeout=10" in info
