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
