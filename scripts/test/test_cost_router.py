"""
scripts/test/test_cost_router.py — dev-mode routing + the Groq-429
FULL-JITTER retry (TestCoverageReview-2026-07-21 gap 1).

The jitter term is load-bearing: FIXES_AND_CLEANUP.md records the live
incident where a bare `2**n * 5` gave every concurrent CI job identical
waits — they retried in lockstep and re-saturated Groq's rate window.
These tests pin the formula `(2**attempt) * 5 + random.uniform(0, 3)` so
a future "cleanup" can't quietly remove the de-synchronization.

No network, no real sleeps: httpx.post, time.sleep, random.uniform and
network_watchdog are all stubbed.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root (runtime/)

import cost_router  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Isolate cwd (circuit_breaker persists under <repo_root>/.agent-rfc/),
    reset the failure tracker, and stub network_watchdog to 'online'."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    cost_router._consecutive_failures.clear()
    watchdog = types.ModuleType("network_watchdog")
    watchdog.is_online = lambda force=False: True  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "network_watchdog", watchdog)
    yield
    cost_router._consecutive_failures.clear()


# ── route(): tier selection ──────────────────────────────────────────────────


def test_offline_routes_local(monkeypatch):
    sys.modules["network_watchdog"].is_online = lambda force=False: False  # type: ignore[attr-defined]
    r = cost_router.route("anything")
    assert r.is_local and r.tier == "local"


def test_force_local_overrides_online():
    r = cost_router.route("anything", force_local=True)
    assert r.is_local


def test_task_type_architect_routes_frontier(monkeypatch):
    monkeypatch.setattr(cost_router, "MODEL_ARCHITECT", "claude-sonnet-4-6")
    r = cost_router.route("short prompt", task_type="architect")
    assert r.tier == "architect"
    assert "anthropic" in r.base_url


def test_architect_keyword_forces_tier():
    r = cost_router.route("beware the race condition in this handler")
    assert r.tier == "architect"


def test_standard_tier_uses_groq_when_key_present(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    r = cost_router.route("write a small helper function")
    assert r.tier == "standard" and "groq" in r.base_url and not r.is_local


def test_standard_tier_falls_back_local_without_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = cost_router.route("write a small helper function")
    assert r.is_local


def test_two_failures_escalate_standard_to_complex(monkeypatch):
    """Escalation policy: only after two consecutive failures (module doc)."""
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setattr(cost_router, "GITHUB_MODELS_TOKEN", "")
    cost_router.record_failure(cost_router.MODEL_STANDARD)
    assert cost_router.route("write a small helper function").tier == "standard"
    cost_router.record_failure(cost_router.MODEL_STANDARD)
    assert cost_router.route("write a small helper function").tier == "complex"
    cost_router.record_success(cost_router.MODEL_STANDARD)
    assert cost_router.route("write a small helper function").tier == "standard"


# ── call(): 429 retry with FULL JITTER ───────────────────────────────────────


class _Resp:
    def __init__(self, status: int) -> None:
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


def _stub_transport(monkeypatch, responses: list[_Resp]):
    import random
    import time as time_mod

    import httpx

    sleeps: list[float] = []
    uniform_calls: list[tuple] = []
    monkeypatch.setattr(time_mod, "sleep", lambda s: sleeps.append(s))

    def fake_uniform(a, b):
        uniform_calls.append((a, b))
        return 1.25

    monkeypatch.setattr(random, "uniform", fake_uniform)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: responses.pop(0))

    groq = cost_router.ModelRoute(
        "llama-3.3-70b-versatile", "https://api.groq.com/openai/v1", "k", "standard"
    )
    monkeypatch.setattr(cost_router, "route", lambda *a, **k: groq)
    return sleeps, uniform_calls


def test_429_retry_full_jitter_formula(monkeypatch):
    sleeps, uniform_calls = _stub_transport(monkeypatch, [_Resp(429), _Resp(429), _Resp(200)])
    assert cost_router.call("hi") == "ok"
    # (2**attempt) * 5 + jitter, attempt = 1, 2 — and jitter drawn from (0, 3)
    assert sleeps == [2 * 5 + 1.25, 4 * 5 + 1.25]
    assert uniform_calls == [(0, 3), (0, 3)]


def test_429_exhaustion_raises_and_records_failure(monkeypatch):
    sleeps, _ = _stub_transport(monkeypatch, [_Resp(429)] * 4)
    with pytest.raises(RuntimeError, match="LLM call failed"):
        cost_router.call("hi")
    # 3 backoffs for 4 attempts; the 4th 429 raises instead of sleeping
    assert len(sleeps) == 3
    assert cost_router._consecutive_failures["llama-3.3-70b-versatile"] == 1


def test_success_resets_failure_counter(monkeypatch):
    cost_router.record_failure("llama-3.3-70b-versatile")
    _stub_transport(monkeypatch, [_Resp(200)])
    assert cost_router.call("hi") == "ok"
    assert "llama-3.3-70b-versatile" not in cost_router._consecutive_failures
