"""Async TTL caches for read-mostly external API data.

The default is deliberately unbounded in entry count: travel data is small and
highly repetitive, and the project owner asked for "no limit" caching. Expired
entries are still purged so an unbounded cache cannot leak memory forever. An
optional ``max_entries`` cap remains available for tests or constrained hosts.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Hashable

# Purge expired entries roughly every N writes even when no cap is configured.
_PURGE_EVERY = 64


class AsyncTTLCache:
    def __init__(self, ttl_seconds: int, *, max_entries: int = 0) -> None:
        self._ttl = ttl_seconds
        # 0 or a negative value means "no artificial entry limit".
        self._max_entries = max_entries
        self._data: dict[Hashable, tuple[float, Any]] = {}
        # Per-key locks prevent a cache stampede. Locks are removed again once
        # nobody is waiting, so this dictionary does not grow without bound.
        self._locks: dict[Hashable, asyncio.Lock] = {}
        self._guard = asyncio.Lock()
        self._writes_since_purge = 0

    @property
    def ttl(self) -> int:
        return self._ttl

    def __len__(self) -> int:
        return len(self._data)

    async def get_or_set(
        self,
        key: Hashable,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        if self._ttl <= 0:
            return await factory()

        now = time.monotonic()
        cached = self._data.get(key)
        if cached and cached[0] > now:
            return cached[1]

        async with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
        try:
            async with lock:
                now = time.monotonic()
                cached = self._data.get(key)
                if cached and cached[0] > now:
                    return cached[1]
                value = await factory()
                expires_at = time.monotonic() + self._ttl
                self._data[key] = (expires_at, value)
                self._writes_since_purge += 1
                self._maybe_purge(now=expires_at)
                return value
        finally:
            # Waiting callers already hold a reference to the lock; removing it
            # here only stops the mapping itself from growing.
            if not lock.locked():
                async with self._guard:
                    if self._locks.get(key) is lock and not lock.locked():
                        self._locks.pop(key, None)

    def _maybe_purge(self, *, now: float) -> None:
        over_cap = self._max_entries > 0 and len(self._data) > self._max_entries
        if not over_cap and self._writes_since_purge < _PURGE_EVERY:
            return
        self._purge(now=now, enforce_cap=over_cap)

    def _purge(self, *, now: float | None = None, enforce_cap: bool = False) -> None:
        current = time.monotonic() if now is None else now
        expired = [key for key, (expires_at, _) in self._data.items() if expires_at <= current]
        for key in expired:
            self._data.pop(key, None)
        if enforce_cap and self._max_entries > 0 and len(self._data) > self._max_entries:
            # Only reached when a caller explicitly configures a cap.
            overflow = len(self._data) - self._max_entries
            for key in sorted(self._data, key=lambda item: self._data[item][0])[:overflow]:
                self._data.pop(key, None)
        # Drop locks whose entries are gone. An in-flight lock is never popped
        # because it is still referenced by its waiter below.
        if len(self._locks) > max(128, len(self._data) * 2):
            live_keys = set(self._data)
            for key, lock in list(self._locks.items()):
                if key not in live_keys and not lock.locked():
                    self._locks.pop(key, None)
        self._writes_since_purge = 0

    def clear(self) -> None:
        self._data.clear()
        self._locks.clear()
        self._writes_since_purge = 0

    def purge_expired(self) -> int:
        """Remove expired entries and return how many were removed."""
        before = len(self._data)
        self._purge()
        return before - len(self._data)
