"""Database access supporting Neon (Lakebase PostgreSQL) and isolated SQLite tests.

PostgreSQL (Neon) is the production database. SQLite support exists only so
local tests and offline development do not require a cloud project. Both drivers
share the same repository SQL, with only parameter/style adaptation here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, Sequence

from app.core.exceptions import DatabaseUnavailableError

logger = logging.getLogger(__name__)

SQLITE_SCHEMA_PATH = Path(__file__).with_name("sqlite_schema.sql")


def _normalise_sqlite_param(value: Any) -> Any:
    if isinstance(value, dict | list):
        return json.dumps(value, separators=(",", ":"))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return int(value)
    return value


def _normalise_pg_param(value: Any) -> Any:
    if isinstance(value, dict | list):
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return value


def sqlite_path_from_dsn(dsn: str) -> str:
    prefix = "sqlite:///"
    if not dsn.startswith(prefix):
        raise ValueError("SQLite DATABASE_URL must look like sqlite:///relative.db")
    path = dsn[len(prefix) :]
    if not path:
        raise ValueError("SQLite DATABASE_URL is missing a file path")
    return path


class SqliteTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _prepare(sql: str, params: Sequence[Any]) -> tuple[str, tuple[Any, ...]]:
        return sql.replace("%s", "?"), tuple(_normalise_sqlite_param(p) for p in params)

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        statement, values = self._prepare(sql, params)
        cursor = await asyncio.to_thread(self._connection.execute, statement, values)
        return cursor.rowcount

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        statement, values = self._prepare(sql, params)
        cursor = await asyncio.to_thread(self._connection.execute, statement, values)
        row = await asyncio.to_thread(cursor.fetchone)
        return dict(row) if row is not None else None

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        statement, values = self._prepare(sql, params)
        cursor = await asyncio.to_thread(self._connection.execute, statement, values)
        rows = await asyncio.to_thread(cursor.fetchall)
        return [dict(row) for row in rows]


class PostgresTransaction:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        cursor = await self._connection.execute(
            sql, tuple(_normalise_pg_param(p) for p in params)
        )
        return cursor.rowcount

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        cursor = await self._connection.execute(
            sql, tuple(_normalise_pg_param(p) for p in params)
        )
        row = await cursor.fetchone()
        return dict(row) if row is not None else None

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        cursor = await self._connection.execute(
            sql, tuple(_normalise_pg_param(p) for p in params)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


class Database:
    # Neon's transaction pooler closes idle TCP connections after a few
    # minutes. Long-lived containers therefore see stale sockets on the first
    # checkout after quiet periods. `check` validates (and silently replaces)
    # such connections, `max_lifetime` rotates them proactively, and TCP
    # keepalives keep the socket healthy through idle stretches. Connection
    # acquisition is additionally retried so a cold Neon compute (which can
    # take several seconds to wake) never surfaces as "database unavailable".
    CONNECT_ATTEMPTS = 4
    CONNECT_BACKOFF_SECONDS = (0.5, 1.0, 2.0, 4.0)
    CHECKOUT_RETRIES = 2

    def __init__(
        self,
        dsn: str,
        *,
        pool_min_size: int = 1,
        pool_max_size: int = 10,
        pool_timeout_seconds: float = 10.0,
    ) -> None:
        self.dsn = dsn
        self.is_sqlite = dsn.startswith("sqlite")
        self._pool_min_size = max(pool_min_size, 1)
        self._pool_max_size = max(pool_max_size, self._pool_min_size)
        self._pool_timeout = pool_timeout_seconds
        self._pool: Any = None
        self._sqlite_path: str | None = sqlite_path_from_dsn(dsn) if self.is_sqlite else None

    @property
    def dialect(self) -> str:
        return "sqlite" if self.is_sqlite else "postgresql"

    def _postgresql_conninfo(self) -> str:
        extra_uri = (
            "connect_timeout=10"
            "&keepalives=1&keepalives_idle=30&keepalives_interval=10"
            "&keepalives_count=3"
        )
        extra_kw = (
            " connect_timeout=10"
            " keepalives=1 keepalives_idle=30 keepalives_interval=10"
            " keepalives_count=3"
        )
        if self.dsn.startswith(("postgresql://", "postgres://", "postgresql+", "postgres+")):
            separator = "&" if "?" in self.dsn else "?"
            return f"{self.dsn}{separator}{extra_uri}"
        return f"{self.dsn}{extra_kw}"

    async def connect(self) -> None:
        if self.is_sqlite:
            assert self._sqlite_path is not None
            if self._sqlite_path != ":memory:":
                Path(self._sqlite_path).expanduser().resolve().parent.mkdir(
                    parents=True, exist_ok=True
                )
            await self.check_health()
            return

        try:
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool, ConnectionPool

            conninfo = self._postgresql_conninfo()
            last_error: Exception | None = None
            for attempt in range(self.CONNECT_ATTEMPTS):
                pool = AsyncConnectionPool(
                    conninfo=conninfo,
                    min_size=self._pool_min_size,
                    max_size=self._pool_max_size,
                    timeout=self._pool_timeout,
                    # Detect and replace sockets that Neon (or any proxy)
                    # silently closed while idle. NOTE: must be the ASYNC
                    # checker — the sync variant fails on async connections,
                    # discarding every connection on checkout.
                    check=AsyncConnectionPool.check_connection,
                    max_lifetime=300.0,
                    max_idle=self._pool_min_size,
                    reconnect_timeout=self._pool_timeout,
                    open=False,
                    kwargs={
                        "row_factory": dict_row,
                        # Safe with Neon's transaction pooler (PgBouncer).
                        "prepare_threshold": None,
                    },
                )
                try:
                    await pool.open(wait=True, timeout=self._pool_timeout)
                except Exception as exc:  # noqa: BLE001 - retried below
                    last_error = exc
                    await self._close_pool_quietly(pool)
                    if attempt < self.CONNECT_ATTEMPTS - 1:
                        delay = self.CONNECT_BACKOFF_SECONDS[attempt]
                        logger.warning(
                            "PostgreSQL connection attempt %s/%s failed (%s); "
                            "retrying in %.1fs",
                            attempt + 1,
                            self.CONNECT_ATTEMPTS,
                            type(exc).__name__,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    break
                # Pool is open: keep it and verify it serves queries.
                self._pool = pool
                await self.check_health()
                return
            raise DatabaseUnavailableError() from last_error
        except DatabaseUnavailableError:
            await self.close()
            raise
        except Exception as exc:
            await self.close()
            logger.error("PostgreSQL connection failed: %s", type(exc).__name__)
            raise DatabaseUnavailableError(
                "Could not connect to the Neon PostgreSQL database."
            ) from exc

    async def _close_pool_quietly(self, pool: Any) -> None:
        try:
            await pool.close(timeout=5.0)
        except Exception:  # pragma: no cover - defensive
            pass

    async def close(self) -> None:
        if self._pool is not None:
            pool, self._pool = self._pool, None
            try:
                await pool.close()
            except Exception:  # pragma: no cover - defensive
                pass

    def _sqlite_connection(self) -> sqlite3.Connection:
        assert self._sqlite_path is not None
        connection = sqlite3.connect(
            self._sqlite_path,
            timeout=10.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[SqliteTransaction | PostgresTransaction]:
        if self.is_sqlite:
            connection = await asyncio.to_thread(self._sqlite_connection)
            try:
                yield SqliteTransaction(connection)
                await asyncio.to_thread(connection.commit)
            except Exception:
                await asyncio.to_thread(connection.rollback)
                raise
            finally:
                await asyncio.to_thread(connection.close)
            return

        if self._pool is None:
            raise DatabaseUnavailableError("Database connection pool is not initialised.")
        try:
            import psycopg
            from psycopg_pool import PoolTimeout
        except ImportError:  # pragma: no cover - psycopg is a hard dependency
            psycopg = None  # type: ignore[assignment]
            PoolTimeout = ()  # type: ignore[assignment]

        for attempt in range(max(self.CHECKOUT_RETRIES, 1)):
            try:
                yielded = False
                async with self._pool.connection() as connection:
                    async with connection.transaction():
                        yielded = True
                        yield PostgresTransaction(connection)
                return
            except DatabaseUnavailableError:
                raise
            except Exception as exc:
                # A checkout/first-connection failure (stale socket after an
                # idle period, cold compute, pool timeout) is retried once
                # transparently. `yielded` is False exactly when the failure
                # happened before the caller's work started, so a retry cannot
                # duplicate side effects.
                if (
                    attempt < self.CHECKOUT_RETRIES - 1
                    and not yielded
                    and (
                        (PoolTimeout and isinstance(exc, PoolTimeout))
                        or (psycopg is not None and isinstance(exc, psycopg.OperationalError))
                    )
                ):
                    logger.warning(
                        "PostgreSQL connection acquisition failed (%s); retrying once",
                        type(exc).__name__,
                    )
                    continue
                if self._is_operational_error(exc):
                    logger.error("PostgreSQL transaction failed: %s", type(exc).__name__)
                    raise DatabaseUnavailableError() from exc
                raise

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        async with self.transaction() as tx:
            return await tx.execute(sql, params)

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        async with self.transaction() as tx:
            return await tx.fetch_one(sql, params)

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        async with self.transaction() as tx:
            return await tx.fetch_all(sql, params)

    @staticmethod
    def _is_operational_error(exc: Exception) -> bool:
        try:
            import psycopg

            if isinstance(exc, psycopg.OperationalError):
                return True
        except ImportError:  # pragma: no cover
            pass
        return isinstance(exc, sqlite3.OperationalError)

    async def check_health(self) -> dict[str, str]:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                async with self.transaction() as tx:
                    await tx.fetch_one("SELECT 1 AS ok")
                return {"status": "up", "dialect": self.dialect}
            except DatabaseUnavailableError:
                raise
            except Exception as exc:  # noqa: BLE001 - surfaced as unavailable
                last_error = exc
                logger.warning(
                    "Database health check attempt %s failed: %s",
                    attempt + 1,
                    type(exc).__name__,
                )
        logger.error("Database health check failed: %s", type(last_error).__name__)
        raise DatabaseUnavailableError() from last_error

    async def initialise_sqlite_schema(self) -> None:
        if not self.is_sqlite:
            raise RuntimeError("Automatic schema creation is only allowed for SQLite")
        schema = await asyncio.to_thread(SQLITE_SCHEMA_PATH.read_text, encoding="utf-8")

        def _execute_script() -> None:
            connection = self._sqlite_connection()
            try:
                connection.executescript(schema)
                connection.commit()
            finally:
                connection.close()

        await asyncio.to_thread(_execute_script)
