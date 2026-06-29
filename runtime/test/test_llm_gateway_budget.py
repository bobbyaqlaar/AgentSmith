"""
runtime/test/test_llm_gateway_budget.py — regression test for the budget
reservation race (FIXES_AND_CLEANUP.md 2.1).

Uses the in-memory backend (no external infra) for the concurrency
assertion — deterministic and fast enough to run on every PR. A separate
manual check (`scripts/verify_system.py --check-idempotency` / `--check-dlq`)
exercises the Postgres backends against a throwaway database, since CI
doesn't have one available by default for this job.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime.llm_gateway import BudgetExceededError, LLMGateway  # noqa: E402


def _make_gateway(
    cap_usd: float, output_cost_per_token: float, input_cost_per_token: float = 0.01
) -> LLMGateway:
    gw = LLMGateway(tenant_id="acme", budget_cap_usd=cap_usd)
    gw.models = {
        "developer": {
            "id": "test-model",
            "cost_per_input_token": input_cost_per_token,
            "cost_per_output_token": output_cost_per_token,
            "degrade_to": None,
        }
    }
    return gw


@pytest.mark.asyncio
async def test_concurrent_calls_cannot_exceed_cap():
    """N concurrent complete() calls for the same tenant must never let
    combined spend exceed the cap — the old check-then-act pattern allowed
    exactly this."""
    gw = _make_gateway(cap_usd=1.0, output_cost_per_token=0.5)

    async def fake_invoke(cfg, messages, max_tokens, temperature):
        await asyncio.sleep(0.02)
        return "ok", 0, 1  # 1 output token -> $0.5 actual cost at this pricing

    gw._invoke = fake_invoke

    async def run_one():
        try:
            return await gw.complete(prompt="hi", model_hint="developer", max_tokens=1)
        except BudgetExceededError as exc:
            return exc

    results = await asyncio.gather(*[run_one() for _ in range(10)])
    succeeded = [r for r in results if not isinstance(r, BudgetExceededError)]
    final_spend = gw._budget.get_spend("acme")

    # Reservation is conservative (estimated_cost includes input cost too),
    # so the exact number that succeed depends on pricing — the invariant
    # under test is that spend never exceeds the cap, not a specific count.
    assert final_spend <= gw.budget_cap_usd + 1e-9, (
        f"budget overshoot: spent ${final_spend} against cap ${gw.budget_cap_usd} "
        f"with {len(succeeded)} succeeding calls — the reservation race regressed"
    )
    assert len(succeeded) >= 1, "at least one call should succeed under a non-zero cap"


@pytest.mark.asyncio
async def test_reservation_releases_on_invoke_failure():
    """If the provider call raises, the reservation must be released —
    otherwise a transient provider error would permanently burn budget."""
    gw = _make_gateway(cap_usd=1.0, output_cost_per_token=0.5)

    async def failing_invoke(cfg, messages, max_tokens, temperature):
        raise RuntimeError("simulated provider failure")

    gw._invoke = failing_invoke

    with pytest.raises(RuntimeError):
        await gw.complete(prompt="hi", model_hint="developer", max_tokens=1)

    assert gw._budget.get_spend("acme") == 0.0, (
        "reservation was not released after invoke() raised"
    )


@pytest.mark.asyncio
async def test_free_tier_model_bypasses_reservation():
    """A free/local-tier model (cost_per_input_token == 0) must never be
    blocked by budget — see LLMGateway._is_free_tier."""
    gw = _make_gateway(cap_usd=0.0, output_cost_per_token=0.0, input_cost_per_token=0.0)

    async def fake_invoke(cfg, messages, max_tokens, temperature):
        return "ok", 5, 5

    gw._invoke = fake_invoke

    result = await gw.complete(prompt="hi", model_hint="developer", max_tokens=10)
    assert result.text == "ok"
    assert gw._budget.get_spend("acme") == 0.0


@pytest.mark.asyncio
async def test_reservation_reconciles_to_actual_cost():
    """The conservative max_tokens-based estimate must be replaced by the
    real cost after the call, not left as the (larger) estimate."""
    # cap must accommodate the conservative max_tokens-based reservation
    # (100 * (0.1 + 0.1) = 20) even though the actual cost will be far less.
    gw = _make_gateway(
        cap_usd=30.0, output_cost_per_token=0.1, input_cost_per_token=0.1
    )

    async def fake_invoke(cfg, messages, max_tokens, temperature):
        return "ok", 1, 1  # actual cost: 1*0.1 + 1*0.1 = 0.2

    gw._invoke = fake_invoke

    await gw.complete(
        prompt="hi", model_hint="developer", max_tokens=100
    )  # estimate: 100*0.2 = 20 (would exceed cap if not reconciled down)

    spend = gw._budget.get_spend("acme")
    assert abs(spend - 0.2) < 1e-9, (
        f"expected spend reconciled to actual cost 0.2, got {spend}"
    )


@pytest.mark.asyncio
async def test_invoke_retries_transient_errors_with_backoff():
    """_invoke() retries httpx.TransportError/429/5xx (the documented but
    previously-unimplemented "Throttle: exponential backoff" degrade-ladder
    step) and gives up after 3 attempts — tenacity was a required
    dependency from the start for exactly this, but nothing called it
    until this test's corresponding fix landed."""
    import httpx
    from unittest.mock import patch

    gw = _make_gateway(
        cap_usd=1000.0, output_cost_per_token=0.0, input_cost_per_token=0.0
    )
    cfg = gw.models["developer"]
    call_count = {"n": 0}

    async def fake_post(self, url, json=None, headers=None):
        call_count["n"] += 1
        request = httpx.Request("POST", url)
        if call_count["n"] < 3:
            response = httpx.Response(503, request=request, text="Service Unavailable")
            raise httpx.HTTPStatusError("503", request=request, response=response)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with patch.object(httpx.AsyncClient, "post", fake_post):
        text, in_tok, out_tok = await gw._invoke(
            cfg, [{"role": "user", "content": "hi"}], 10, 0.2
        )

    assert call_count["n"] == 3, (
        f"expected 2 failed attempts + 1 success, got {call_count['n']} attempts"
    )
    assert text == "ok"


@pytest.mark.asyncio
async def test_invoke_does_not_retry_non_transient_errors():
    """A 401 (bad credentials) or any other non-429/5xx error fails on the
    first attempt — retrying it would waste the attempt budget on a
    failure that can't succeed differently the second time."""
    import httpx
    from unittest.mock import patch

    gw = _make_gateway(
        cap_usd=1000.0, output_cost_per_token=0.0, input_cost_per_token=0.0
    )
    cfg = gw.models["developer"]
    call_count = {"n": 0}

    async def fake_post_401(self, url, json=None, headers=None):
        call_count["n"] += 1
        request = httpx.Request("POST", url)
        response = httpx.Response(401, request=request, text="invalid api key")
        raise httpx.HTTPStatusError("401", request=request, response=response)

    with (
        patch.object(httpx.AsyncClient, "post", fake_post_401),
        pytest.raises(httpx.HTTPStatusError) as exc_info,
    ):
        await gw._invoke(cfg, [{"role": "user", "content": "hi"}], 10, 0.2)

    assert exc_info.value.response.status_code == 401
    assert call_count["n"] == 1, (
        f"expected exactly 1 attempt (no retry on 401), got {call_count['n']}"
    )


@pytest.mark.asyncio
async def test_invoke_groq_provider_uses_groq_base_url_and_key():
    """provider: groq resolves to Groq's OpenAI-compatible endpoint and
    GROQ_API_KEY by default — not the generic OpenAI fallback's
    api.openai.com/OPENAI_API_KEY, which would silently send Groq-shaped
    requests to the wrong host with the wrong key."""
    import httpx
    from unittest.mock import patch

    gw = _make_gateway(
        cap_usd=1000.0, output_cost_per_token=0.0, input_cost_per_token=0.0
    )
    cfg = {
        "id": "llama-3.3-70b-versatile",
        "provider": "groq",
        "cost_per_input_token": 0,
        "cost_per_output_token": 0,
    }
    seen = {}

    async def fake_post(self, url, json=None, headers=None):
        seen["url"] = url
        seen["headers"] = headers
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with (
        patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test_key"}),
        patch.object(httpx.AsyncClient, "post", fake_post),
    ):
        text, _, _ = await gw._invoke(cfg, [{"role": "user", "content": "hi"}], 10, 0.2)

    assert text == "ok"
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer gsk_test_key"
