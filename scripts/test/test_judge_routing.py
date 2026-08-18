"""
scripts/test/test_judge_routing.py — a configurable judge must reach the
provider it declares, and the registry merge must not leak one model's fields
onto another.

Background: the judge role is meant to be swappable between vendors (Anthropic,
xAI, Google) because judge/actor independence is weakest when both sides share
a training lineage — `judge_independence_warning` only catches IDENTICAL ids,
so a Claude judge grading a Claude analyst reads as independent when it is not.

Two defects blocked that, both silent:

  * `cost_router._route_for_model` substring-matched the model id and fell
    through to localhost Ollama for anything unrecognised, so `grok-4` and
    `gemini-2.5-pro` were served by a local model under their own names.
  * `load_model_registry` shallow-merged a tenant role over the framework's, so
    a tenant judge inherited `endpoint`, `cost_per_*_token` and `degrade_to`
    from a model that had nothing to do with it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import cost_router  # noqa: E402
import _shared  # noqa: E402


def _tenant_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, yaml_body: str) -> None:
    (tmp_path / ".git").mkdir(exist_ok=True)
    (tmp_path / "models.yaml").write_text(yaml_body, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _shared._REGISTRY_CACHE.clear()


# ── Routing follows the registry, not the model name ─────────────────────────


@pytest.mark.parametrize(
    "provider,model,env,expected_host",
    [
        ("xai", "grok-4", "XAI_API_KEY", "https://api.x.ai/v1"),
        (
            "google_ai",
            "gemini-2.5-pro",
            "GEMINI_API_KEY",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        ),
        ("anthropic", "claude-opus-4-8", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1"),
    ],
)
def test_declared_judge_reaches_its_own_provider(
    tmp_path, monkeypatch, provider, model, env, expected_host
) -> None:
    """Before this, only ids containing 'claude'/'gpt'/'llama' routed anywhere
    but localhost — a Grok judge was quietly served by Ollama."""
    _tenant_registry(
        tmp_path, monkeypatch,
        f"models:\n  judge:\n    id: {model}\n    provider: {provider}\n",
    )
    monkeypatch.setenv(env, "probe-key")

    route = cost_router._route_for_model(model)
    assert route.base_url == expected_host
    assert route.api_key == "probe-key"
    assert not route.is_local


def test_a_models_yaml_endpoint_overrides_the_provider_default(tmp_path, monkeypatch) -> None:
    """Proxies, region-pinned hosts and gateways — the reason `endpoint` exists."""
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: grok-4\n    provider: xai\n"
        "    endpoint: https://llm-proxy.internal/v1\n",
    )
    monkeypatch.setenv("XAI_API_KEY", "k")
    assert cost_router._route_for_model("grok-4").base_url == "https://llm-proxy.internal/v1"


def test_per_role_api_key_env_is_honoured(tmp_path, monkeypatch) -> None:
    """Judge/actor separation extended to billing: the judge's own account."""
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: grok-4\n    provider: xai\n"
        "    api_key_env: XAI_API_KEY_JUDGE\n",
    )
    monkeypatch.setenv("XAI_API_KEY", "actor-key")
    monkeypatch.setenv("XAI_API_KEY_JUDGE", "judge-key")
    assert cost_router._route_for_model("grok-4").api_key == "judge-key"


def test_an_undeclared_model_still_falls_back_to_the_heuristics(tmp_path, monkeypatch) -> None:
    """Registry-first must not break ids nobody declared — shadow-eval and
    AGENT_JUDGE_MODEL one-offs still pass a bare model name."""
    _tenant_registry(tmp_path, monkeypatch, "models: {}\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert cost_router._route_for_model("claude-opus-4-8").base_url == (
        "https://api.anthropic.com/v1"
    )


# ── Registry merge: a different model inherits nothing ───────────────────────


def test_a_tenant_judge_does_not_inherit_the_framework_endpoint(tmp_path, monkeypatch) -> None:
    """The live bug. KYC Sentinel's judge (claude-opus-4-8 / anthropic) merged
    over the framework's (falcon3:3b / ollama) and inherited
    `endpoint: ${OLLAMA_BASE_URL}/v1`, so the gateway posted Claude requests at
    the Ollama host."""
    from runtime.llm_gateway import load_model_registry

    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: claude-opus-4-8\n    provider: anthropic\n",
    )
    judge = load_model_registry()["judge"]
    assert judge["id"] == "claude-opus-4-8"
    assert judge["provider"] == "anthropic"
    assert "endpoint" not in judge, f"inherited a foreign endpoint: {judge.get('endpoint')!r}"


def test_a_tenant_judge_does_not_inherit_free_tier_costs(tmp_path, monkeypatch) -> None:
    """Inheriting an Ollama tier's zeros makes a frontier model read as
    costless to budget reservation and the spend cap."""
    from runtime.llm_gateway import load_model_registry

    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: grok-4\n    provider: xai\n"
        "    cost_per_input_token: 0.000003\n",
    )
    assert load_model_registry()["judge"]["cost_per_input_token"] == 0.000003


def test_omitting_degrade_to_actually_removes_it(tmp_path, monkeypatch) -> None:
    """Phase 2 removed `degrade_to` from KYC's judge; the framework's value
    still showed through the merge, so the judge kept degrading — to the
    framework's target rather than the tenant's. A judge must be able to
    declare no fallback (a substituted grader is not a grader)."""
    from runtime.llm_gateway import load_model_registry, LLMGateway

    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: claude-opus-4-8\n    provider: anthropic\n",
    )
    reg = load_model_registry()
    assert "degrade_to" not in reg["judge"]

    gw = LLMGateway.__new__(LLMGateway)
    gw.models = reg
    assert gw._degrade_chain("judge") == ["judge"]


def test_same_id_still_merges(tmp_path, monkeypatch) -> None:
    """Replacement is scoped to a CHANGED id. Tweaking one field on the
    framework's own route must still inherit the rest."""
    from runtime.llm_gateway import load_model_registry

    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: falcon3:3b\n    cost_per_input_token: 0.5\n",
    )
    judge = load_model_registry()["judge"]
    assert judge["cost_per_input_token"] == 0.5
    assert judge["provider"] == "ollama"       # inherited
    assert judge["endpoint"]                    # inherited


# ── Per-judge thresholds ─────────────────────────────────────────────────────


def _run_evals():
    from _shared import load_script

    mod = load_script("run-evals")
    return mod


def test_threshold_can_be_declared_beside_the_judge(tmp_path, monkeypatch) -> None:
    """0.80 from one judge is not 0.80 from another. With a swappable judge, a
    single global threshold compares each new grader against the last one's
    calibration."""
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: grok-4\n    provider: xai\n    fail_below: 0.78\n",
    )
    monkeypatch.delenv("EVAL_FAIL_BELOW", raising=False)
    assert _run_evals()._resolve_fail_below("golden", None) == 0.78


def test_threshold_can_differ_per_suite(tmp_path, monkeypatch) -> None:
    """A pair-parity bar and a correctness bar are not the same number."""
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: grok-4\n    provider: xai\n"
        "    fail_below:\n      golden: 0.78\n      fairness: 0.85\n",
    )
    revals = _run_evals()
    assert revals._resolve_fail_below("golden", None) == 0.78
    assert revals._resolve_fail_below("fairness", None) == 0.85


def test_cli_still_wins_over_the_registry(tmp_path, monkeypatch) -> None:
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: grok-4\n    provider: xai\n    fail_below: 0.78\n",
    )
    assert _run_evals()._resolve_fail_below("golden", 0.9) == 0.9


# ── An unusable judge is an error, not a score of zero ───────────────────────


def _fake_call(monkeypatch, reply: str) -> None:
    import cost_router

    monkeypatch.setattr(cost_router, "call", lambda *a, **k: reply)


def test_the_judge_grades_at_temperature_zero(monkeypatch) -> None:
    """The router's default is 0.2, which is right for an actor and wrong for
    its grader: sampling noise in the judge is indistinguishable from a quality
    change in the thing being judged, and it lands on the threshold.

    Measured on KYC Sentinel's suites on 2026-08-17, four passes each against
    identical deterministic output — only the grader varied:

        golden    0.846 – 0.971 (spread .125) at 0.2  →  spread .076 at 0.0
        halluc.   0.883 – 0.945 (spread .062) at 0.2  →  spread .055 at 0.0

    A gate cannot sit inside a band that wide without changing colour on
    unchanged input, and a gate that flips gets re-run until it is green.

    This asserts the argument is actually passed. The call site omitted it for
    the framework's whole history and silently took the actor default, which is
    exactly the kind of omission that leaves no trace in any output.
    """
    import cost_router
    import eval_judge

    seen: dict = {}

    def _capture(*args, **kwargs):
        seen.update(kwargs)
        return '{"correctness": 1, "tool_accuracy": 1, "score": 1.0}'

    monkeypatch.setattr(cost_router, "call", _capture)
    eval_judge.run_judge("prompt", "some-judge")

    assert "temperature" in seen, "the judge must not inherit the actor default"
    assert seen["temperature"] == 0.0


def test_an_empty_verdict_is_reported_as_a_judge_error(monkeypatch) -> None:
    """falcon3:3b — the framework's DEFAULT judge — returns an empty string to
    a JSON-only scoring prompt (verified against a local Ollama with the model
    pulled; qwen2.5 answers the same prompt correctly).

    That used to produce score 0.0 with no `error`, which is the difference
    between "the judge said nothing" and "your output is worthless". The
    scorecard reported the second, and because run-evals.py's all-errored skip
    keys off `error`, an unusable judge failed the gate as a quality
    regression — every case 0.00, notes blank.
    """
    import eval_judge

    _fake_call(monkeypatch, "")
    scored = eval_judge.run_judge("prompt", "falcon3:3b")

    assert scored["score"] == 0.0
    assert scored["error"], "an unparseable verdict must set `error`"
    assert "no parseable JSON" in scored["error"]
    assert "empty response" in scored["error"]


def test_prose_without_json_is_also_an_error(monkeypatch) -> None:
    """A chatty model that ignores 'JSON only' is unusable in the same way."""
    import eval_judge

    _fake_call(monkeypatch, "Sure! I'd rate this quite highly overall.")
    scored = eval_judge.run_judge("prompt", "chatty-model")
    assert scored["error"] and "no parseable JSON" in scored["error"]


def test_a_real_verdict_sets_no_error(monkeypatch) -> None:
    import eval_judge

    _fake_call(monkeypatch, '{"correctness": 1, "tool_accuracy": 1, "score": 0.9}')
    scored = eval_judge.run_judge("prompt", "good-judge")
    assert scored["score"] == 0.9
    assert not scored.get("error")
    assert scored["judged_by"] == "good-judge"


def test_declared_api_key_env_falls_back_to_the_provider_default(tmp_path, monkeypatch) -> None:
    """`api_key_env` is an opt-in override, not a hard requirement.

    KYC Sentinel's judge declares ANTHROPIC_API_KEY_JUDGE so a quota exhaustion
    on the actor's account cannot also take out its reviewer, and documents that
    it falls back to ANTHROPIC_API_KEY when the dedicated one is unset. Reading
    only the declared name sends an EMPTY auth header and 401s every call.
    """
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: claude-opus-4-8\n    provider: anthropic\n"
        "    api_key_env: ANTHROPIC_API_KEY_JUDGE\n",
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY_JUDGE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "shared-account-key")

    route = cost_router._route_for_model("claude-opus-4-8")
    assert route.api_key == "shared-account-key", (
        "an unset api_key_env must fall back, not produce an empty auth header"
    )


def test_the_dedicated_key_still_wins_when_populated(tmp_path, monkeypatch) -> None:
    _tenant_registry(
        tmp_path, monkeypatch,
        "models:\n  judge:\n    id: claude-opus-4-8\n    provider: anthropic\n"
        "    api_key_env: ANTHROPIC_API_KEY_JUDGE\n",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "actor-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY_JUDGE", "judge-key")
    assert cost_router._route_for_model("claude-opus-4-8").api_key == "judge-key"
