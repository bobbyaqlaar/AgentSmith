"""
runtime/idempotency.py — Idempotency key store and deduplication.

Every LLM Gateway activity is assigned an idempotency key derived from
a hash of its input parameters. Duplicate submissions (on retry after crash)
are detected and short-circuited — the cached result is returned immediately.

WHAT THIS GUARANTEES, PRECISELY. `get` then `set` is check-then-act with no
reservation between them, so this suppresses SEQUENTIAL duplicates — the retry
after a crash, which is the case above and the common one — and NOT concurrent
ones. Two workers handed the same task at the same time both miss the cache and
both do the work, including both paid LLM calls. Closing that needs a
reservation (`SET NX` / `INSERT ... ON CONFLICT DO NOTHING`) and a decision
about what the loser does — block, poll, or refuse — which is a semantics
change rather than a fix, so it is stated here rather than quietly assumed away.

Backend: Redis (default) or Postgres. Configurable via IDEMPOTENCY_BACKEND env var.

Usage:
    store = IdempotencyStore()
    result = store.get("sha256:abc123")
    if result is not None:
        return result  # cached
    # ... do the work ...
    store.set("sha256:abc123", result, ttl_seconds=86400)

See SPECS.md §25 for the full specification.
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
            self._backend: Any = _RedisBackend()
        elif backend == "postgres":
            self._backend = _PostgresBackend()
        else:
            raise ValueError(
                f"Unknown IDEMPOTENCY_BACKEND={backend!r}. Use 'redis' or 'postgres'."
            )

    def get(self, key: str) -> Optional[Any]:
        """Return cached result for key, or None if not found / expired."""
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        """Store result for key with TTL."""
        self._backend.set(key, value, ttl_seconds)

    def purge_expired(self) -> int:
        """Delete rows past their TTL. Returns the count, or -1 when the
        backend expires its own keys.

        Redis does (`ex=`), Postgres does not — `expires_at` is only consulted
        by `get`. -1 rather than 0 so "this backend needs no purge" is not
        reported as "nothing needed purging", which is the same value meaning
        two things that pillar 15 is about.
        """
        purge = getattr(self._backend, "purge_expired", None)
        return purge() if callable(purge) else -1


class _RedisBackend:
    def __init__(self) -> None:
        import redis  # type: ignore

        self._client = redis.from_url(os.environ["REDIS_URL"])

    def get(self, key: str) -> Optional[Any]:
        raw = self._client.get(f"agenticframework:idempotency:{key}")
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        self._client.set(
            f"agenticframework:idempotency:{key}",
            json.dumps(value, default=str),
            ex=ttl_seconds,
        )


_IDEMPOTENCY_DDL = """
    CREATE TABLE IF NOT EXISTS idempotency_keys (
        key        TEXT PRIMARY KEY,
        value      JSONB NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL
    )
"""


class _PostgresBackend:
    def __init__(self) -> None:
        self._dsn = os.environ["DATABASE_URL"]
        # Once per DSN per process. This ran on every construction, and
        # LLMGateway builds an IdempotencyStore per instance — see
        # pg_pool.ensure_schema for why a no-op CREATE TABLE still costs.
        from runtime.pg_pool import ensure_schema

        ensure_schema(self._dsn, _IDEMPOTENCY_DDL, key="idempotency_keys")

    def _connect(self):
        # Pooled (runtime/pg_pool.py) — .close() releases to the pool, so
        # the `finally: conn.close()` call sites below stay correct as-is.
        from runtime.pg_pool import connect as pg_connect
        return pg_connect(self._dsn)

    def get(self, key: str) -> Optional[Any]:
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM idempotency_keys WHERE key = %s AND expires_at > now()",
                    (key,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                # json.dumps + cast to jsonb rather than passing the dict
                # directly: psycopg2 has no implicit Python-dict-to-jsonb
                # adapter registered by default.
                cur.execute(
                    """
                    INSERT INTO idempotency_keys (key, value, expires_at)
                    VALUES (%s, %s::jsonb, now() + (%s || ' seconds')::interval)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (key, json.dumps(value, default=str), ttl_seconds),
                )
        finally:
            conn.close()

    def purge_expired(self) -> int:
        """Deletes rows past their TTL.

        `expires_at` is only ever read in `get`'s WHERE clause, so an expired
        row stops being *returned* and never stops *existing*: this table grows
        by one row per gateway call, forever, and nothing deleted from it.

        The previous version of this docstring named
        `scripts/verify_system.py --check-idempotency` as a caller. That check
        does not call this, and neither did anything else — the method had no
        caller at all. It is reachable as `agentsmith purge-idempotency` now,
        and listed as a Day-2 task in OPERATIONS.md §9, because a cleanup job
        nobody is told to run is not a cleanup job.
        """
        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("DELETE FROM idempotency_keys WHERE expires_at <= now()")
                return cur.rowcount
        finally:
            conn.close()
