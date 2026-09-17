"""
runtime/test/test_idempotency_boundary.py — the idempotency row is parsed, not
trusted (.agent-rfc/designs/idempotency-row-boundary.md).

A row is JSON written by whichever build was deployed, with a 24-hour TTL, so
every deploy that changes `CompletionResult` leaves a day of rows shaped for a
different one. Unpacking such a row used to fall into the generic `except`,
which logs "idempotency lookup failed" and re-runs the model: the duplicate-call
guarantee quietly stops holding, the tenant pays twice, and the log line reads
like a database outage.

These tests pin the three things that fixes: the row is validated, a refused row
is a miss with its OWN message, and the store being unreachable still reads as
the infrastructure failure it is.
"""

from __future__ import annotations

import logging

import pytest

from runtime.llm_gateway import CACHE_SCHEMA_VERSION, CompletionResult, _CachedCompletion


def _result(**over) -> CompletionResult:
    fields = dict(text="hello", model_used="m", input_tokens=3, output_tokens=5, cost_usd=0.01)
    fields.update(over)
    return CompletionResult(**fields)


# ── the row is a declared shape ──────────────────────────────────────────────


def test_a_row_round_trips_through_the_boundary_model() -> None:
    result = _result(guardrail_counts={"card": 1}, prompt_guard_reasons=["looks like an override"])

    row = _CachedCompletion.from_result(result).model_dump()
    back = _CachedCompletion.model_validate(row).to_result()

    assert back == result
    assert row["v"] == CACHE_SCHEMA_VERSION


def test_the_row_carries_only_declared_fields() -> None:
    """`result.__dict__` would carry whatever was set on the instance; a private
    attribute added later must not leak into the store."""
    result = _result()
    result._internal_note = "not for the wire"

    row = _CachedCompletion.from_result(result).model_dump()

    assert "_internal_note" not in row


def test_every_field_of_the_result_is_on_the_row() -> None:
    """Adding a field to one and not the other would silently drop it on every
    cache hit (`pin-unremovable-duplicates`)."""
    from dataclasses import fields as dataclass_fields

    assert {f.name for f in dataclass_fields(CompletionResult)} == set(_CachedCompletion.model_fields) - {"v"}


# ── what a row that does not match does ──────────────────────────────────────


def test_a_legacy_row_without_a_version_is_still_read() -> None:
    """Rows written before this change are exactly the old `__dict__`; they have
    the same field names, so they validate and are used."""
    legacy = _result().__dict__.copy()

    assert _CachedCompletion.model_validate(legacy).to_result() == _result()


def test_a_row_from_a_newer_build_is_refused_rather_than_guessed_at() -> None:
    row = _CachedCompletion.from_result(_result()).model_dump()
    row["v"] = CACHE_SCHEMA_VERSION + 1

    with pytest.raises(ValueError, match="newer"):
        _CachedCompletion.model_validate(row)


def test_a_row_with_an_unexpected_field_is_refused() -> None:
    row = _CachedCompletion.from_result(_result()).model_dump()
    row["renamed_since"] = "x"

    with pytest.raises(ValueError):
        _CachedCompletion.model_validate(row)


def test_a_row_with_the_wrong_type_is_refused() -> None:
    """`json.dumps(..., default=str)` turns what it cannot encode into a string;
    unvalidated, that string became a typed field with no error at all."""
    row = _CachedCompletion.from_result(_result()).model_dump()
    row["cost_usd"] = "not a number"

    with pytest.raises(ValueError):
        _CachedCompletion.model_validate(row)


def test_a_row_missing_a_required_field_is_refused() -> None:
    row = _CachedCompletion.from_result(_result()).model_dump()
    del row["text"]

    with pytest.raises(ValueError):
        _CachedCompletion.model_validate(row)


# ── what the gateway does with one ───────────────────────────────────────────


class _Store:
    """The idempotency store, holding whatever row the test wants to serve."""

    def __init__(self, row, fail: bool = False) -> None:
        self.row, self.fail, self.written = row, fail, []

    def get(self, key):
        if self.fail:
            raise RuntimeError("connection refused")
        return self.row

    def set(self, key, value, ttl_seconds: int = 86400) -> None:
        self.written.append(value)


@pytest.fixture()
def gateway(monkeypatch):
    from runtime import llm_gateway

    client = llm_gateway.LLMGateway.__new__(llm_gateway.LLMGateway)
    client.tenant_id = "t1"
    return client


def test_a_good_row_is_served_from_the_cache(gateway, monkeypatch) -> None:
    store = _Store(_CachedCompletion.from_result(_result()).model_dump())

    assert gateway_cached(gateway, store, monkeypatch) == _result()


def test_a_stale_row_reads_as_a_miss_and_says_which(gateway, monkeypatch, caplog) -> None:
    """The message a person reads must separate 'this row is from another
    version' from 'the store is down'."""
    row = _CachedCompletion.from_result(_result()).model_dump()
    row["cost_usd"] = "not a number"
    store = _Store(row)

    with caplog.at_level(logging.WARNING):
        served = gateway_cached(gateway, store, monkeypatch)

    assert served is None, "a row that cannot be parsed is a miss, not a result"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "cost_usd" in messages
    assert "idempotency lookup failed" not in messages, "that line is for the store being down"


def test_the_store_being_unreachable_still_reads_as_infrastructure(gateway, monkeypatch, caplog) -> None:
    store = _Store(None, fail=True)

    with caplog.at_level(logging.ERROR):
        served = gateway_cached(gateway, store, monkeypatch)

    assert served is None
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_moderation_still_runs_on_a_cache_hit(gateway, monkeypatch) -> None:
    """SEC-MOD-001: a newly registered or stricter hook must not be bypassable
    by asking the same question twice. The code said so in a comment and
    nothing held it — this refactor moved that line, and a refactor that drops
    it must fail here."""
    from runtime import llm_gateway

    seen = []

    def moderator(text, raise_on_block=False):
        seen.append(text)

    store = _Store(_CachedCompletion.from_result(_result(text="cached answer")).model_dump())
    gateway._idempotency = store
    monkeypatch.setattr(llm_gateway, "apply_output_moderation", moderator)

    llm_gateway.LLMGateway._cached_completion(gateway, "sha256:abc")

    assert seen == ["cached answer"]


def test_a_blocked_cache_hit_raises_rather_than_being_served(gateway, monkeypatch) -> None:
    from runtime import llm_gateway

    def blocking(text, raise_on_block=False):
        raise llm_gateway.ModerationBlockedError("blocked")

    store = _Store(_CachedCompletion.from_result(_result()).model_dump())
    gateway._idempotency = store
    monkeypatch.setattr(llm_gateway, "apply_output_moderation", blocking)

    with pytest.raises(llm_gateway.ModerationBlockedError):
        llm_gateway.LLMGateway._cached_completion(gateway, "sha256:abc")


def test_what_is_written_is_the_declared_row(gateway, monkeypatch) -> None:
    store = _Store(None)
    gateway._idempotency = store

    from runtime import llm_gateway

    llm_gateway.LLMGateway._cache_completion(gateway, "sha256:abc", _result())

    assert store.written and store.written[0]["v"] == CACHE_SCHEMA_VERSION
    assert set(store.written[0]) == set(_CachedCompletion.model_fields)


def gateway_cached(client, store, monkeypatch):
    """The cache-read path, isolated: it is what `complete()` calls first."""
    from runtime import llm_gateway

    client._idempotency = store
    monkeypatch.setattr(llm_gateway, "apply_output_moderation", lambda *a, **k: None)
    return llm_gateway.LLMGateway._cached_completion(client, "sha256:abc")
