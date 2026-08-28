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

import cost_router


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


# ── Judge credential resolution (eval path) ──────────────────────────────────


def test_forced_model_honours_a_registry_role_api_key_env(
    monkeypatch, tmp_path
) -> None:
    """The eval judge routes through _route_for_model, which read
    ANTHROPIC_API_KEY only. A tenant whose judge declares its own
    `api_key_env` — KYC Sentinel's does, for judge/actor separation at the
    billing level — passed the eval preflight (which checks the DECLARED
    variable, correctly) and then sent an empty auth header. 401 on every
    judge call, from a configuration that is right everywhere else."""
    import importlib

    import _shared

    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  judge:\n"
        "    id: claude-opus-4-8\n"
        "    provider: anthropic\n"
        "    api_key_env: ANTHROPIC_API_KEY_JUDGE\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY_JUDGE", "sk-declared")
    _shared._REGISTRY_CACHE.clear()
    router = importlib.reload(cost_router)

    route = router._route_for_model("claude-opus-4-8")
    assert route.api_key == "sk-declared"
    assert route.base_url == "https://api.anthropic.com/v1"


def test_declared_key_wins_over_the_provider_default(monkeypatch, tmp_path) -> None:
    import importlib

    import _shared

    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  judge:\n"
        "    id: claude-opus-4-8\n"
        "    provider: anthropic\n"
        "    api_key_env: ANTHROPIC_API_KEY_JUDGE\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fallback")
    monkeypatch.setenv("ANTHROPIC_API_KEY_JUDGE", "sk-declared")
    _shared._REGISTRY_CACHE.clear()
    router = importlib.reload(cost_router)

    assert router._route_for_model("claude-opus-4-8").api_key == "sk-declared"


def test_provider_default_still_used_without_a_declared_env(
    monkeypatch, tmp_path
) -> None:
    """Roles with no api_key_env must keep working off the provider default —
    the fix must not require every tenant to declare one."""
    import importlib

    import _shared

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fallback")
    monkeypatch.delenv("ANTHROPIC_API_KEY_JUDGE", raising=False)
    _shared._REGISTRY_CACHE.clear()
    router = importlib.reload(cost_router)

    assert router._route_for_model("claude-sonnet-4-6").api_key == "sk-fallback"


def test_local_model_ids_route_to_ollama(monkeypatch, tmp_path) -> None:
    """The framework's default judge is falcon3:3b — an id _route_for_model
    recognises via none of its substring rules, so it must land on the local
    fallback rather than an unauthenticated cloud host."""
    import importlib

    import _shared

    _shared._REGISTRY_CACHE.clear()
    router = importlib.reload(cost_router)

    for model in ("falcon3:3b", "qwen2.5", "smollm2", "llama3.2:3b"):
        route = router._route_for_model(model)
        assert route.is_local, f"{model} should route locally, got {route.base_url}"
        assert route.api_key == "ollama"


# ── Provider error bodies must reach the caller ──────────────────────────────


def test_http_error_surfaces_the_provider_response_body(monkeypatch) -> None:
    """`raise_for_status()` reports only the status line, so a 400 arrived as
    "Client error '400 Bad Request'" with no hint at WHICH field was wrong.
    KYC Sentinel's eval gate failed twelve times that way with nothing to act
    on. Providers put the actionable part in the body — surface it."""
    import httpx

    class _ErrResp:
        status_code = 400
        text = (
            '{"type":"error","error":{"type":"invalid_request_error",'
            '"message":"max_tokens: must be less than or equal to 8192"},'
            '"request_id":"req_abc"}'
        )

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _ErrResp())
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    with pytest.raises(RuntimeError) as exc:
        cost_router.call("hi", force_model="llama-3.3-70b-versatile")

    message = str(exc.value)
    assert "HTTP 400" in message
    assert "max_tokens: must be less than or equal to 8192" in message
    assert "req_abc" in message


def test_http_error_without_a_body_still_reports_the_status(monkeypatch) -> None:
    """Response doubles and bodiless errors must not turn into an
    AttributeError that masks the real status code."""
    import httpx

    class _BodilessResp:
        status_code = 503

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _BodilessResp())
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")

    with pytest.raises(RuntimeError, match="HTTP 503"):
        cost_router.call("hi", force_model="llama-3.3-70b-versatile")


# ── A provider that reports no usage must not be silently unmetered ──────────
#
# runtime/provider_dispatch.parse_response returns Optional[int]: a response
# with no `usage` block yields None rather than a fabricated 0. cost_router
# handed that straight to audit_token_velocity_circuit, whose arithmetic raised
# TypeError into a blanket `except Exception: pass` — so the call counted
# toward neither the 5-minute burst window nor the monthly cap, and nothing was
# printed, logged or raised.
#
# runtime/llm_gateway.py's sibling path already warned and billed the reserved
# estimate for exactly this response shape. This call site is in another
# package, which is the whole reason it was missed (review-levers 4.5: when a
# fix lands, grep for the siblings).


class _RespNoUsage(_Resp):
    def json(self) -> dict:
        return {"choices": [{"message": {"content": "ok"}}]}  # no usage block


def _record_audits(monkeypatch):
    import circuit_breaker

    calls: list[tuple] = []
    monkeypatch.setattr(
        circuit_breaker,
        "audit_token_velocity_circuit",
        lambda *a, **k: calls.append(a),
    )
    return calls


def test_a_response_without_usage_never_reaches_the_circuit_breaker(monkeypatch, capsys):
    _stub_transport(monkeypatch, [_RespNoUsage(200)])
    calls = _record_audits(monkeypatch)

    assert cost_router.call("hi") == "ok"  # the call itself still succeeds

    assert calls == [], f"None token counts were passed to the breaker: {calls}"
    err = capsys.readouterr().err
    assert "no usage block" in err and "NOT counted" in err, (
        "the call went unmetered and nothing said so"
    )


def test_a_normal_response_is_still_metered(monkeypatch):
    """The other half — the guard must not have turned metering off."""
    _stub_transport(monkeypatch, [_Resp(200)])
    calls = _record_audits(monkeypatch)

    assert cost_router.call("hi") == "ok"
    assert calls == [(1, 1)]


def test_a_tripped_breaker_does_not_fail_a_call_the_provider_already_answered(
    monkeypatch, capsys
):
    """The trip is reported, not swallowed and not raised.

    The provider has already been called and paid for by the time the breaker
    runs here, so there is nothing left to break — but the blanket
    `except Exception: pass` that used to catch it also caught the TypeError
    above, for as long as it stood.
    """
    import circuit_breaker

    _stub_transport(monkeypatch, [_Resp(200)])

    def _trip(*_a, **_k):
        raise circuit_breaker.CircuitBreakerTripped("BURST", "over the window")

    monkeypatch.setattr(circuit_breaker, "audit_token_velocity_circuit", _trip)

    assert cost_router.call("hi") == "ok"
    assert "over the window" in capsys.readouterr().err


def test_a_breaker_fault_is_reported_rather_than_swallowed(monkeypatch, capsys):
    import circuit_breaker

    _stub_transport(monkeypatch, [_Resp(200)])

    def _boom(*_a, **_k):
        raise RuntimeError("cache is on fire")

    monkeypatch.setattr(circuit_breaker, "audit_token_velocity_circuit", _boom)

    assert cost_router.call("hi") == "ok"  # still fail-open
    err = capsys.readouterr().err
    assert "bookkeeping failed" in err and "cache is on fire" in err
