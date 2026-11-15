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
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._pool_timeout = pool_timeout_seconds
        self._pool: Any = None
        self._sqlite_path: str | None = sqlite_path_from_dsn(dsn) if self.is_sqlite else None

    @property
    def dialect(self) -> str:
        return "sqlite" if self.is_sqlite else "postgresql"

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
            from psycopg_pool import AsyncConnectionPool

            self._pool = AsyncConnectionPool(
                conninfo=self.dsn,
                min_size=self._pool_min_size,
                max_size=self._pool_max_size,
                timeout=self._pool_timeout,
                open=False,
                kwargs={
                    "row_factory": dict_row,
                    # Safe with Neon's transaction pooler (PgBouncer).
                    "prepare_threshold": None,
                },
            )
            await self._pool.open(wait=True, timeout=self._pool_timeout)
            await self.check_health()
        except DatabaseUnavailableError:
            await self.close()
            raise
        except Exception as exc:
            await self.close()
            logger.error("PostgreSQL connection failed: %s", type(exc).__name__)
            raise DatabaseUnavailableError(
                "Could not connect to the Neon PostgreSQL database."
            ) from exc

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

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
            async with self._pool.connection() as connection:
                async with connection.transaction():
                    yield PostgresTransaction(connection)
        except DatabaseUnavailableError:
            raise
        except Exception as exc:
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
        try:
            async with self.transaction() as tx:
                await tx.fetch_one("SELECT 1 AS ok")
            return {"status": "up", "dialect": self.dialect}
        except Exception as exc:
            logger.error("Database health check failed: %s", type(exc).__name__)
            raise DatabaseUnavailableError() from exc

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
