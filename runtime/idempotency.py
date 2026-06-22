"""
runtime/idempotency.py — Idempotency key store and deduplication.

Every LLM Gateway activity is assigned an idempotency key derived from
a hash of its input parameters. Duplicate submissions (on retry after crash)
are detected and short-circuited — the cached result is returned immediately.

Backend: Redis (default) or Postgres. Configurable via IDEMPOTENCY_BACKEND env var.

Usage:
    store = IdempotencyStore()
    result = store.get("sha256:abc123")
    if result is not None:
        return result  # cached
    # ... do the work ...
    store.set("sha256:abc123", result, ttl_seconds=86400)

See SPECS.md §25 for the full specification.

TODO (Phase 2):
  - Implement Redis backend
  - Implement Postgres backend
  - Add TTL cleanup
  - Wire into llm_gateway.py
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional


def make_key(payload: Any) -> str:
    """Derive a stable idempotency key from any JSON-serialisable payload."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyStore:
    """
    Idempotency key store.

    Instantiate once per worker process; share across gateway calls.
    """

    def __init__(self) -> None:
        backend = os.environ.get("IDEMPOTENCY_BACKEND", "redis").lower()
        if backend == "redis":
            self._backend = _RedisBackend()
        elif backend == "postgres":
            self._backend = _PostgresBackend()
        else:
            raise ValueError(f"Unknown IDEMPOTENCY_BACKEND={backend!r}. Use 'redis' or 'postgres'.")

    def get(self, key: str) -> Optional[Any]:
        """Return cached result for key, or None if not found / expired."""
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        """Store result for key with TTL."""
        self._backend.set(key, value, ttl_seconds)


class _RedisBackend:
    def get(self, key: str) -> Optional[Any]:
        # TODO Phase 2: connect to Redis via REDIS_URL
        raise NotImplementedError("Redis backend not yet implemented.")

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        raise NotImplementedError("Redis backend not yet implemented.")


class _PostgresBackend:
    def get(self, key: str) -> Optional[Any]:
        # TODO Phase 2: connect to Postgres via DATABASE_URL
        raise NotImplementedError("Postgres backend not yet implemented.")

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        raise NotImplementedError("Postgres backend not yet implemented.")
