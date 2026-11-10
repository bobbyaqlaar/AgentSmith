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
        assert gw._budget.get_spend("run-tokens:t:run-1") == 50
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
    assert gw._budget.get_spend("run-tokens:t:run-1") == 0


@pytest.mark.asyncio
async def test_unreported_usage_keeps_the_reservation_as_the_charge():
    gw = _gateway(answer=("ok", None, None))
    with config.override(**{"limits.run_tokens": 10_000}):
        await gw.complete("hi", model_hint="developer", workflow_id="run-1", max_tokens=200)
    assert gw._budget.get_spend("run-tokens:t:run-1") == tl.estimate_tokens([{"role": "user", "content": "hi"}]) + 200


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
    monkeypatch.setenv(tl.RUN_TOKENS_ENV, "not a number")
    assert tl.run_token_limit() is None
