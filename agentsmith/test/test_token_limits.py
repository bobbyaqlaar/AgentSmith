"""Tokens bounded per role and per run (.agent-rfc/designs/run-token-limits.md)."""

from __future__ import annotations

import pytest

from agentsmith import config, token_limits as tl
from agentsmith.llm_gateway import _MemoryBudgetBackend
from agentsmith.test._gateway_fixtures import fake_gateway
from agentsmith.tool_registry import ToolRegistry

LONG = "x" * 4_000  # about 1,000 tokens


def _gateway(model: dict | None = None, answer=("ok", 30, 20)):
    gw = fake_gateway(model={"id": "m", "provider": "openai", "cost_per_input_token": 0.0,
                             "cost_per_output_token": 0.0, **(model or {})}, invoke=answer)
    gw._budget = _MemoryBudgetBackend()
    return gw


def test_an_undeclared_limit_changes_nothing():
    assert tl.output_cap({}, 4096) == 4096
    tl.check_input({}, [{"role": "user", "content": LONG * 50}], "developer")
    assert tl.reserve_run(_MemoryBudgetBackend(), "t", "run-1", "hi", 100) == 0


@pytest.mark.asyncio
async def test_the_role_caps_the_answer():
    gw = _gateway({"max_output_tokens": 300})
    await gw.complete("hi", model_hint="developer", max_tokens=4096)
    assert gw._invoke.await_args.args[2] == 300
    await gw.complete("hi", model_hint="developer", max_tokens=100)
    assert gw._invoke.await_args.args[2] == 100


@pytest.mark.asyncio
async def test_an_oversized_prompt_is_refused_before_it_is_sent():
    gw = _gateway({"max_input_tokens": 500})
    with pytest.raises(tl.ContextTooLargeError, match=r"max_input_tokens"):
        await gw.complete(LONG, model_hint="developer")
    gw._invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_run_stops_at_its_token_budget_and_settles_to_the_real_count():
    gw = _gateway(answer=("ok", 30, 20))
    with config.override(**{"limits.run_tokens": 600}):
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=200)
        # Settled to the real 50, not the ~200 estimate, so a second call still fits.
        assert tl.run_spent(gw._budget, "t", "run-1") == 50
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=200)
        with pytest.raises(tl.RunLimitExceededError, match=r"limits\.run_tokens"):
            await gw.complete(LONG * 2, model_hint="developer", workflow_id="run-1", max_tokens=200)
        assert gw._invoke.await_count == 2
        # Another run has its own budget.
        await gw.complete("hi", model_hint="developer", workflow_id="run-2", max_tokens=200)


@pytest.mark.asyncio
async def test_a_failed_call_spends_nothing_against_the_run():
    gw = _gateway()
    gw._invoke.side_effect = ValueError("bad prompt")
    with config.override(**{"limits.run_tokens": 600}), pytest.raises((ValueError, RuntimeError)):
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=200)
    assert tl.run_spent(gw._budget, "t", "run-1") == 0


@pytest.mark.asyncio
async def test_unreported_usage_keeps_the_reservation_as_the_charge():
    gw = _gateway(answer=("ok", None, None))
    with config.override(**{"limits.run_tokens": 10_000}):
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=200)
    assert tl.run_spent(gw._budget, "t", "run-1") == tl.estimate_tokens([{"role": "user", "content": "hi"}]) + 200


def test_a_run_stops_at_its_tool_call_limit():
    registry = ToolRegistry(tenant_id="t", strict=False)
    registry.register(lambda: "found", name="lookup")
    with config.override(**{"limits.run_tool_calls": 2}):
        registry.invoke("lookup", {}, run_id="run-1")
        registry.invoke("lookup", {}, run_id="run-1")
        with pytest.raises(tl.ToolCallLimitExceededError, match=r"limits\.run_tool_calls"):
            registry.invoke("lookup", {}, run_id="run-1")
        registry.invoke("lookup", {}, run_id="run-2")
        registry.invoke("lookup", {})  # no run named: not counted


def test_the_environment_declares_a_limit_too(monkeypatch):
    monkeypatch.setenv(tl.RUN_TOKENS_ENV, "1234")
    assert tl.run_token_limit() == 1234
    monkeypatch.setenv(tl.RUN_TOKENS_ENV, "")
    assert tl.run_token_limit() is None  # declared empty is not declared


# ── The 4.1.0 release review: R1, R4, R5, R6, R20 ──


@pytest.mark.parametrize("value", ["100k", "not a number", True, 0, -5, 1.5])
def test_a_limit_that_cannot_be_read_is_refused_not_dropped(monkeypatch, value):
    """R4: `100k` was no limit at all and `true` capped every answer at 1 token."""
    monkeypatch.setenv(tl.RUN_TOKENS_ENV, str(value))
    with pytest.raises(tl.LimitUnreadableError, match=tl.RUN_TOKENS_ENV):
        tl.run_token_limit()
    with pytest.raises(tl.LimitUnreadableError, match="max_output_tokens"):
        tl.output_cap({"max_output_tokens": value}, 4096)
    with pytest.raises(tl.LimitUnreadableError, match="max_input_tokens"):
        tl.check_input({"max_input_tokens": value}, "hi", "developer")


@pytest.mark.asyncio
async def test_a_call_the_money_cap_refuses_spends_nothing_against_the_run():
    """R1: the run reserved 600, the cost cap refused, and the 600 stayed spent."""
    from agentsmith.llm_gateway import BudgetExceededError, BudgetStatus

    gw = _gateway({"cost_per_input_token": 1.0, "cost_per_output_token": 1.0})
    gw._is_free_tier.return_value = False
    gw.budget_cap_usd = 1.0
    gw.get_budget_status = lambda: BudgetStatus(tenant_id="t", spent_usd=0.0, cap_usd=1.0, period_start="2026-11-01")
    with config.override(**{"limits.run_tokens": 1000}):
        with pytest.raises(BudgetExceededError):
            await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=600)
        assert tl.run_spent(gw._budget, "t", "run-1") == 0
        with pytest.raises(BudgetExceededError):
            await gw.complete_stream("hi", model_hint="developer", workflow_id="run-1", max_tokens=600)
        assert tl.run_spent(gw._budget, "t", "run-1") == 0


@pytest.mark.asyncio
async def test_a_call_with_no_tier_to_try_spends_nothing_against_the_run():
    """R1: the `text is None` exit kept the reservation too."""
    gw = _gateway()
    gw._degrade_chain.return_value = ["not-configured"]
    with config.override(**{"limits.run_tokens": 1000}), pytest.raises(RuntimeError, match="No configured model tier"):
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=200)
    assert tl.run_spent(gw._budget, "t", "run-1") == 0


@pytest.mark.asyncio
async def test_a_fallback_tier_is_held_to_its_own_caps():
    """R5: the degraded-to role's caps were never read."""
    gw = _gateway()
    gw.models["local"] = {"id": "small", "provider": "ollama", "max_output_tokens": 512,
                          "max_input_tokens": 4000}
    gw._degrade_chain.return_value = ["developer", "local"]
    gw._is_provider_exhausted = lambda exc: True
    gw._invoke.side_effect = [RuntimeError("credit balance is too low"), ("ok", 30, 20)]
    await gw.complete("hi", model_hint="developer", max_tokens=4096)
    assert gw._invoke.await_args.args[2] == 512

    gw._invoke.reset_mock()
    gw._invoke.side_effect = [RuntimeError("credit balance is too low"), ("ok", 30, 20)]
    with pytest.raises(tl.ContextTooLargeError, match="'local'"):
        await gw.complete(LONG * 5, model_hint="developer", max_tokens=100)
    assert gw._invoke.await_count == 1


@pytest.mark.asyncio
async def test_a_stream_that_falls_back_keeps_its_data_class_and_user_and_one_reservation(monkeypatch):
    """R20: the fallback to complete() dropped data_class and user_id, and reserved twice."""
    from unittest.mock import AsyncMock

    gw = _gateway()
    gw._is_provider_exhausted = lambda exc: True
    seen: dict = {}

    async def fallback(prompt, **kwargs):
        seen.update(kwargs, spent=tl.run_spent(gw._budget, "t", "run-1"))
        return "answer"

    monkeypatch.setattr(gw, "complete", AsyncMock(side_effect=fallback))

    class Broken:
        def __init__(self, *a, **k):
            raise RuntimeError("credit balance is too low")

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", Broken)
    gw._resolve_endpoint = lambda cfg: ("http://localhost:1", "k")
    with config.override(**{"limits.run_tokens": 10_000}):
        assert await gw.complete_stream("hi", model_hint="developer", workflow_id="run-1", max_tokens=200,
                                        data_class="open", user_id="u1") == "answer"
    assert seen["data_class"] == "open" and seen["user_id"] == "u1"
    assert seen["spent"] == 0  # the stream's reservation was released before complete() reserved its own


def test_run_counters_are_their_own_store_and_are_forgotten():
    """R6: one key per run for the life of the process, in the money table, keyed by month."""
    backend = _MemoryBudgetBackend()
    with config.override(**{"limits.run_tokens": 10_000}):
        for n in range(1000):
            tl.reserve_run(backend, "t", f"run-{n}", "hi", 10)
    assert backend._spend == {}  # the money ledger holds money only
    counters = tl.run_counters(backend)
    assert len(counters._values) == 1000
    counters.prune(now=counters._clock() + tl.RUN_TTL_SECONDS + 1)
    assert counters._values == {}


@pytest.mark.asyncio
async def test_an_unreadable_cap_on_a_fallback_tier_is_named_not_wrapped():
    gw = _gateway()
    gw.models["local"] = {"id": "small", "provider": "ollama", "max_output_tokens": "512k"}
    gw._degrade_chain.return_value = ["developer", "local"]
    gw._is_provider_exhausted = lambda exc: "credit" in str(exc)
    gw._invoke.side_effect = [RuntimeError("credit balance is too low"), ("ok", 30, 20)]
    with pytest.raises(tl.LimitUnreadableError, match="max_output_tokens"):
        await gw.complete("hi", model_hint="developer", max_tokens=100)


@pytest.mark.asyncio
async def test_a_call_the_run_budget_refuses_spends_no_money():
    """R1's mirror: the run refuses after the money cap reserved, so the money is given back."""
    from agentsmith.llm_gateway import BudgetStatus

    gw = _gateway({"cost_per_input_token": 0.001, "cost_per_output_token": 0.001})
    gw._is_free_tier.return_value = False
    gw.get_budget_status = lambda: BudgetStatus(tenant_id="t", spent_usd=0.0, cap_usd=10.0, period_start="2026-11-01")
    with config.override(**{"limits.run_tokens": 100}), pytest.raises(tl.RunLimitExceededError):
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=600)
    assert gw._budget.get_spend("t") == 0


# ── The 4.1.0 review's second pass: P2-R1 (.agent-rfc/designs/stream-release-and-lockout.md) ──


@pytest.mark.asyncio
async def test_a_stream_that_cannot_be_built_gives_back_what_it_reserved():
    """P2-R1: the request was built outside the try that releases, so an error there kept
    the run's tokens and the tenant's money although nothing was sent."""
    from agentsmith.llm_gateway import BudgetStatus

    gw = _gateway({"provider": "anthropic", "cost_per_input_token": 0.001, "cost_per_output_token": 0.001})
    gw._is_free_tier.return_value = False
    gw.get_budget_status = lambda: BudgetStatus(tenant_id="t", spent_usd=0.0, cap_usd=100.0, period_start="2026-11-01")
    cached = {"type": "text", "text": "be brief", "cache_control": {"type": "ephemeral"}}
    blocks = [{"role": "system", "content": [cached]}, {"role": "user", "content": "hi"}]
    with config.override(**{"limits.run_tokens": 10_000}), pytest.raises(TypeError):
        await gw.complete_stream(blocks, model_hint="developer", workflow_id="run-1", max_tokens=500)
    assert tl.run_spent(gw._budget, "t", "run-1") == 0
    assert gw._budget.get_spend("t") == 0


@pytest.mark.asyncio
async def test_a_stream_refused_by_the_compliance_guard_or_the_run_gives_everything_back(monkeypatch):
    """Two exits the second pass found untested: a refusal after the reservations."""
    from agentsmith.compliance import ComplianceRefused
    from agentsmith.llm_gateway import BudgetStatus

    gw = _gateway({"cost_per_input_token": 0.001, "cost_per_output_token": 0.001})
    gw._is_free_tier.return_value = False
    gw.get_budget_status = lambda: BudgetStatus(tenant_id="t", spent_usd=0.0, cap_usd=100.0, period_start="2026-11-01")

    def refuse(*a, **k):
        raise ComplianceRefused("OB-X", "no")

    monkeypatch.setattr(gw, "_compliance_guard", refuse)
    with config.override(**{"limits.run_tokens": 10_000}), pytest.raises(ComplianceRefused):
        await gw.complete_stream("hi", model_hint="developer", workflow_id="run-1", max_tokens=500)
    assert tl.run_spent(gw._budget, "t", "run-1") == 0 and gw._budget.get_spend("t") == 0
    with config.override(**{"limits.run_tokens": 100}), pytest.raises(tl.RunLimitExceededError):
        await gw.complete_stream("hi", model_hint="developer", workflow_id="run-2", max_tokens=500)
    assert gw._budget.get_spend("t") == 0
