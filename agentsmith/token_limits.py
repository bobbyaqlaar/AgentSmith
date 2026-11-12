"""agentsmith/token_limits.py — tokens bounded per role and per run
(.agent-rfc/designs/run-token-limits.md).

Counting tokens is not the same as using fewer. These limits are off until a tenant
declares them, and each refuses before anything is sent:

    models.yaml  max_output_tokens   the answer, capped per role
                 max_input_tokens    a prompt estimated larger is refused
    tenant.yaml  limits.run_tokens       one workflow run's token budget
                 limits.run_tool_calls   one workflow run's tool calls

Run counters live in their own store, chosen to match the gateway's budget backend
(in process, Redis or Postgres) so they are shared exactly as widely as the spend cap.
Each reserve is atomic, so concurrent calls in one run cannot overshoot. A run's
counters are forgotten `RUN_TTL_SECONDS` after its last call, and carry no month: a run
that crosses the 1st keeps its count. A size known only after the call is estimated
before it at four characters a token.

A limit that is declared but cannot be read is refused with `LimitUnreadableError`,
never read as no limit (the 4.1.0 release review, R4).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

RUN_TOKENS_ENV = "AGENTSMITH_RUN_TOKEN_LIMIT"
RUN_TOOL_CALLS_ENV = "AGENTSMITH_RUN_TOOL_CALL_LIMIT"


class ContextTooLargeError(ValueError):
    """A prompt larger than its role's declared `max_input_tokens`."""


class RunLimitExceededError(RuntimeError):
    """A workflow run would pass its declared token budget."""


class ToolCallLimitExceededError(RuntimeError):
    """A workflow run would pass its declared tool-call limit."""


class LimitUnreadableError(ValueError):
    """A limit was declared, but not as a positive whole number."""


def estimate_tokens(messages: Any) -> int:
    from agentsmith.prompt_identity import content_text

    if isinstance(messages, str):
        return len(messages) // 4
    total = 0
    for message in messages or []:
        content = message.get("content") if isinstance(message, dict) else message
        total += len(content_text(content))
    return total // 4


def _positive(value: Any, name: str) -> Optional[int]:
    """None when the limit is not declared; the number when it is a positive whole
    number; otherwise a refusal naming the setting. `100k` and `true` are not limits."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    number: Optional[int] = None
    if isinstance(value, int) and not isinstance(value, bool):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    if number is None or number <= 0:
        raise LimitUnreadableError(
            f"{name} is {value!r}, which is not a positive whole number of tokens. Write it as digits "
            "(100000, not 100k), or remove it to have no limit.")
    return number


def output_cap(cfg: dict, requested: int) -> int:
    cap = _positive(cfg.get("max_output_tokens"), "max_output_tokens (models.yaml)")
    return min(requested, cap) if cap else requested


def check_input(cfg: dict, messages: Any, role: str) -> None:
    cap = _positive(cfg.get("max_input_tokens"), "max_input_tokens (models.yaml)")
    if cap is None:
        return
    size = estimate_tokens(messages)
    if size > cap:
        raise ContextTooLargeError(
            f"role {role!r} accepts at most {cap} input tokens (max_input_tokens in models.yaml); this prompt is "
            f"about {size}. Send less: summarise the history, or retrieve fewer passages.")


def check_declared_caps(models: dict) -> None:
    """Read both caps of every role, so a cap that cannot be read stops the gateway when it
    starts rather than when a call first reaches that role: on a fallback tier that is the
    failover itself (the 4.1.0 review's second pass, P2-R2)."""
    for role, cfg in (models or {}).items():
        if not isinstance(cfg, dict):
            continue
        for key in ("max_output_tokens", "max_input_tokens"):
            _positive(cfg.get(key), f"{key} of role {role!r} (models.yaml)")


def _limit(dotted: str, env_var: str) -> Optional[int]:
    from agentsmith.config import resolve

    return _positive(resolve(dotted, env_var=env_var, default=None), f"{dotted} (or {env_var})")


def run_token_limit() -> Optional[int]:
    return _limit("limits.run_tokens", RUN_TOKENS_ENV)


def run_tool_call_limit() -> Optional[int]:
    return _limit("limits.run_tool_calls", RUN_TOOL_CALLS_ENV)


RUN_TTL_SECONDS = 2 * 86_400  # a run's counters outlive its last call by two days


class _MemoryRunCounters:
    """One process's run counters, forgotten after `RUN_TTL_SECONDS` without a call."""

    _PRUNE_EVERY = 60.0

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._values: dict[str, list[float]] = {}  # key -> [count, last touched]
        self._lock = threading.Lock()
        self._clock = clock
        self._pruned = clock()

    def prune(self, now: Optional[float] = None) -> None:
        moment = self._clock() if now is None else now
        with self._lock:
            for key in [k for k, (_v, at) in self._values.items() if moment - at > RUN_TTL_SECONDS]:
                del self._values[key]
            self._pruned = moment

    def _touch(self, key: str, delta: float, limit: Optional[float]) -> bool:
        moment = self._clock()
        if moment - self._pruned > self._PRUNE_EVERY:
            self.prune(moment)
        with self._lock:
            current = self._values.get(key, [0.0, moment])[0]
            if limit is not None and current + delta > limit:
                return False
            self._values[key] = [current + delta, moment]
            return True

    def try_reserve(self, key: str, amount: float, limit: float) -> bool:
        return self._touch(key, amount, limit)

    def add(self, key: str, delta: float) -> None:
        self._touch(key, delta, None)

    def get(self, key: str) -> float:
        with self._lock:
            return self._values.get(key, [0.0, 0.0])[0]


class _RedisRunCounters:
    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _key(key: str) -> str:
        return f"agenticframework:{key}"

    def try_reserve(self, key: str, amount: float, limit: float) -> bool:
        name = self._key(key)
        total = float(self._client.incrbyfloat(name, amount))
        self._client.expire(name, RUN_TTL_SECONDS)
        if total > limit:
            self._client.incrbyfloat(name, -amount)
            return False
        return True

    def add(self, key: str, delta: float) -> None:
        name = self._key(key)
        self._client.incrbyfloat(name, delta)
        self._client.expire(name, RUN_TTL_SECONDS)

    def get(self, key: str) -> float:
        value = self._client.get(self._key(key))
        return float(value) if value else 0.0


_RUN_DDL = """
    CREATE TABLE IF NOT EXISTS llm_gateway_run_counters (
        run_key    TEXT PRIMARY KEY,
        spent      DOUBLE PRECISION NOT NULL DEFAULT 0,
        touched_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""


class _PostgresRunCounters:
    """Not the money table: a run is not a tenant, and its row is deleted once stale."""

    _PRUNE_EVERY = 3600.0

    def __init__(self, dsn: str) -> None:
        from agentsmith.pg_pool import ensure_schema

        self._dsn = dsn
        self._pruned = 0.0
        ensure_schema(dsn, _RUN_DDL, key="llm_gateway_run_counters")

    def _run(self, sql: str, params: tuple) -> Optional[tuple]:
        from agentsmith.pg_pool import connect

        conn = connect(self._dsn)
        try:
            with conn, conn.cursor() as cur:
                if time.monotonic() - self._pruned > self._PRUNE_EVERY:
                    cur.execute("DELETE FROM llm_gateway_run_counters WHERE touched_at < now() - "
                                "make_interval(secs => %s)", (RUN_TTL_SECONDS,))
                    self._pruned = time.monotonic()
                cur.execute(sql, params)
                return cur.fetchone() if cur.description else None
        finally:
            conn.close()

    def try_reserve(self, key: str, amount: float, limit: float) -> bool:
        if amount > limit:
            return False
        row = self._run(
            "INSERT INTO llm_gateway_run_counters AS c (run_key, spent) VALUES (%s, %s) "
            "ON CONFLICT (run_key) DO UPDATE SET spent = c.spent + EXCLUDED.spent, touched_at = now() "
            "WHERE c.spent + EXCLUDED.spent <= %s RETURNING spent",
            (key, amount, limit))
        return row is not None

    def add(self, key: str, delta: float) -> None:
        self._run(
            "INSERT INTO llm_gateway_run_counters AS c (run_key, spent) VALUES (%s, %s) "
            "ON CONFLICT (run_key) DO UPDATE SET spent = c.spent + EXCLUDED.spent, touched_at = now()",
            (key, delta))

    def get(self, key: str) -> float:
        row = self._run("SELECT spent FROM llm_gateway_run_counters WHERE run_key = %s", (key,))
        return float(row[0]) if row else 0.0


_counters_lock = threading.Lock()


def run_counters(backend: Any) -> Any:
    """The run counters that go with this budget backend: shared as widely as it is."""
    with _counters_lock:
        counters = getattr(backend, "_run_counters", None)
        if counters is None:
            kind = type(backend).__name__
            if kind == "_RedisBudgetBackend":
                counters = _RedisRunCounters(backend._client)
            elif kind == "_PostgresBudgetBackend":
                counters = _PostgresRunCounters(backend._dsn)
            else:
                counters = _MemoryRunCounters()
            backend._run_counters = counters
        return counters


def _run_key(kind: str, tenant_id: str, run_id: str) -> str:
    return f"run-{kind}:{tenant_id}:{run_id}"


def run_spent(backend: Any, tenant_id: str, run_id: str) -> float:
    """What this run has spent (or reserved) against its token budget."""
    return run_counters(backend).get(_run_key("tokens", tenant_id, run_id))


def reserve_run(backend: Any, tenant_id: str, run_id: Optional[str], messages: Any, max_tokens: int) -> int:
    """Reserve this call's estimate against the run's budget; the amount reserved, or 0
    when the run has no budget. Raises when the call would pass it."""
    limit = run_token_limit()
    if limit is None or not run_id:
        return 0
    estimate = estimate_tokens(messages) + max_tokens
    counters = run_counters(backend)
    if not counters.try_reserve(_run_key("tokens", tenant_id, run_id), estimate, limit):
        spent = counters.get(_run_key("tokens", tenant_id, run_id))
        raise RunLimitExceededError(
            f"run {run_id!r} has spent about {int(spent)} of its {limit} tokens (limits.run_tokens); this call "
            f"would need about {estimate} more. Stopped before it was sent.")
    return estimate


def settle_run(backend: Any, tenant_id: str, run_id: Optional[str], reserved: int,
               input_tokens: Optional[int], output_tokens: Optional[int]) -> None:
    """Replace the estimate with the real count. With no usage reported the estimate stands."""
    if not reserved or not run_id or input_tokens is None or output_tokens is None:
        return
    delta = int(input_tokens) + int(output_tokens) - reserved
    if delta:
        run_counters(backend).add(_run_key("tokens", tenant_id, run_id), delta)


def release_run(backend: Any, tenant_id: str, run_id: Optional[str], reserved: int) -> None:
    """A call that failed spent nothing against the run."""
    if reserved and run_id:
        run_counters(backend).add(_run_key("tokens", tenant_id, run_id), -reserved)


def reserve_tool_call(backend: Any, tenant_id: str, run_id: Optional[str]) -> None:
    limit = run_tool_call_limit()
    if limit is None or not run_id:
        return
    if not run_counters(backend).try_reserve(_run_key("tools", tenant_id, run_id), 1, limit):
        raise ToolCallLimitExceededError(
            f"run {run_id!r} has made its {limit} tool calls (limits.run_tool_calls). Stopped before the next.")
