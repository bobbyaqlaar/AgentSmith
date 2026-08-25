"""
scripts/test/test_circuit_breaker.py — dual-tier financial circuit breaker
(TestCoverageReview-2026-07-21 gap 2). A guardrail with cash consequences
had zero tests.

Covers: burst-window trip, monthly-cap trip, month rollover reset,
rolling-window expiry, and state persistence across calls. All state is
isolated to a tmp repo root (the breaker persists under
<repo_root>/.agent-rfc/fixtures/token_velocity_cache.json).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/

import circuit_breaker  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    # Deterministic limits regardless of the host's env (module reads env at
    # import time, so patch the module attributes, not the env).
    monkeypatch.setattr(circuit_breaker, "BURST_TOKEN_LIMIT", 1000)
    monkeypatch.setattr(circuit_breaker, "MONTHLY_USD_CAP", 1.0)
    monkeypatch.setattr(circuit_breaker, "COST_PER_INPUT_TOKEN", 0.001)
    monkeypatch.setattr(circuit_breaker, "COST_PER_OUTPUT_TOKEN", 0.001)
    yield


def _audit(in_tok: int, out_tok: int) -> None:
    circuit_breaker.audit_token_velocity_circuit(in_tok, out_tok, notify=False)


def test_under_limits_passes_and_persists():
    _audit(100, 100)
    _audit(100, 100)
    status = circuit_breaker.get_status()
    assert status["burst_tokens_5min"] == 400
    assert status["monthly_spend_usd"] == pytest.approx(0.4)
    assert status["current_month"] != ""


def test_burst_trip():
    _audit(300, 300)
    with pytest.raises(circuit_breaker.CircuitBreakerTripped) as exc:
        _audit(300, 300)  # 1200 tokens in window > 1000
    assert exc.value.tier == "BURST"


def test_burst_window_expiry(monkeypatch):
    """Tokens older than the 5-minute window must not count."""
    monkeypatch.setattr(circuit_breaker, "MONTHLY_USD_CAP", 100.0)  # burst-only test
    real_time = time.time()
    monkeypatch.setattr(time, "time", lambda: real_time - 400)  # 400s ago
    _audit(300, 300)
    monkeypatch.setattr(time, "time", lambda: real_time)
    _audit(300, 300)  # old 600 tokens fell out of the window — no trip
    assert circuit_breaker.get_status()["burst_tokens_5min"] == 600


def test_monthly_trip_independent_of_burst(monkeypatch):
    monkeypatch.setattr(circuit_breaker, "BURST_TOKEN_LIMIT", 10_000_000)
    _audit(300, 300)  # $0.6
    with pytest.raises(circuit_breaker.CircuitBreakerTripped) as exc:
        _audit(300, 300)  # $1.2 > $1.0
    assert exc.value.tier == "MONTHLY"
    # The tripping event's spend was still recorded before the raise
    assert circuit_breaker.get_status()["monthly_spend_usd"] == pytest.approx(1.2)


def test_month_rollover_resets_accumulator(monkeypatch):
    monkeypatch.setattr(circuit_breaker, "BURST_TOKEN_LIMIT", 10_000_000)
    _audit(300, 300)  # $0.6 this month
    # Simulate a state written last month
    state = circuit_breaker._load_state()
    state["current_month_identifier"] = "1999-01"
    circuit_breaker._save_state(state)
    _audit(300, 300)  # would be $1.2 cumulative — but rollover resets first
    status = circuit_breaker.get_status()
    assert status["monthly_spend_usd"] == pytest.approx(0.6)
    assert status["current_month"] != "1999-01"


def test_reset_monthly():
    _audit(100, 100)
    circuit_breaker.reset_monthly()
    status = circuit_breaker.get_status()
    assert status["monthly_spend_usd"] == 0.0


def test_corrupt_state_file_recovers(tmp_path):
    """A corrupted cache must degrade to empty state, not crash the call."""
    cache = circuit_breaker._cache_path()
    cache.write_text("{not json")
    _audit(10, 10)  # must not raise
    assert circuit_breaker.get_status()["burst_tokens_5min"] == 20


# ── Tripping a tier is not a reason to un-record the spend (pass 14) ──────────
#
# The burst check used to sit between "append the event" and "add this call's
# cost to the month", and it raises. So a burst-tripping call had its TOKENS
# recorded and its DOLLARS dropped: the monthly accumulator silently skipped
# every call that tripped tier 1 — the heaviest bursts, which are the ones the
# cap most needs to see. The money was already spent; the provider had answered
# before this function ran.
#
# The existing monthly tests could not see it. test_monthly_trip_independent_
# of_burst raises BURST_TOKEN_LIMIT to 10,000,000 precisely to keep tier 1 out
# of the way, and test_burst_trip asserts the tier and nothing about spend — so
# the two tiers were each covered alone and never in the combination where they
# interact.


def test_a_burst_trip_still_bills_the_month():
    _audit(300, 300)  # $0.6, under the 1000-token window
    before = circuit_breaker.get_status()["monthly_spend_usd"]

    with pytest.raises(circuit_breaker.CircuitBreakerTripped) as exc:
        _audit(300, 300)  # 1200 tokens in the window — trips BURST
    assert exc.value.tier == "BURST"

    after = circuit_breaker.get_status()["monthly_spend_usd"]
    assert after == pytest.approx(before + 0.6), (
        "the burst-tripped call's tokens were recorded but its cost was not — "
        f"monthly went {before} -> {after}"
    )


def test_every_burst_tripped_call_is_still_on_the_ledger(monkeypatch):
    """The cumulative shape of it. Three $0.80 calls, the last two of which
    trip tier 1 — the month owes $2.40 either way, because all three reached
    the provider. Under the old order the ledger showed $0.80 and the two
    expensive calls were free."""
    monkeypatch.setattr(circuit_breaker, "MONTHLY_USD_CAP", 100.0)  # tier 2 out of the way
    for _ in range(3):
        try:
            _audit(400, 400)  # 800 tokens each; the window limit is 1000
        except circuit_breaker.CircuitBreakerTripped as exc:
            assert exc.tier == "BURST"

    assert circuit_breaker.get_status()["monthly_spend_usd"] == pytest.approx(2.4), (
        "calls that tripped the burst tier were dropped from the monthly ledger"
    )


# ── An absent token count is not a token count ───────────────────────────────


def test_none_token_counts_are_refused_by_name():
    """runtime/provider_dispatch.parse_response returns Optional[int] since the
    usage-reporting fix — a provider that omits its `usage` block gives None.

    Reaching the arithmetic with None raised TypeError, and every caller wraps
    this in a fail-open handler, so the call went unmetered on BOTH tiers with
    nothing said. A named refusal is something a call site can act on;
    scripts/cost_router.py now does.
    """
    with pytest.raises(ValueError, match="token counts"):
        circuit_breaker.audit_token_velocity_circuit(None, None, notify=False)
    with pytest.raises(ValueError, match="token counts"):
        circuit_breaker.audit_token_velocity_circuit(10, None, notify=False)


# ── The empty state must actually be empty ───────────────────────────────────


def test_a_fresh_empty_state_carries_no_events():
    """`dict(_EMPTY_STATE)` is a shallow copy: the dict is new, the `events`
    list is the module-level constant's own. One append mutated it, and every
    later "empty" state came back holding the previous run's events — on
    exactly the path the fallback exists for, a missing or unwritable cache."""
    first = circuit_breaker._load_state()
    first["events"].append({"ts": 1.0, "input_tokens": 5, "output_tokens": 5})

    second = circuit_breaker._load_state()
    assert second["events"] == [], (
        "a freshly loaded empty state carries events appended to an earlier one"
    )
    assert circuit_breaker._EMPTY_STATE["events"] == []
