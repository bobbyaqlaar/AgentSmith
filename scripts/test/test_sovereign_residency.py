"""
scripts/test/test_sovereign_residency.py — SEC-SOV-001's runner actually bites.

A residency control that cannot fail is worse than no control: it produces an
evidence pack asserting in-border operation on the strength of a check that
would have passed either way. Every case below is a way a sovereign profile
leaks, and each must produce `fail`.

The leak that motivated the whole approach is `test_a_role_that_degrades_out_of_
country_fails`: the primary endpoint is in-border and stays in-border, so a live
probe of it reports healthy forever, while the ladder underneath ends at a
hosted API the moment the primary is overloaded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from security.registry import ControlSpec  # noqa: E402
from security.runners import sovereign_residency as sov  # noqa: E402

CONTROL = ControlSpec(
    id="SEC-SOV-001",
    title="Sovereign residency",
    status="met",
    owner="tenant",
    frameworks={},
    runner="sovereign_residency",
    check_type="unit",
    mechanism="test",
)


def _ollama(degrade_to=None) -> dict:
    return {
        "id": "falcon3:3b",
        "provider": "ollama",
        "endpoint": "${OLLAMA_BASE_URL}/v1",
        "degrade_to": degrade_to,
    }


# ── The template as shipped ───────────────────────────────────────────────────


def test_the_shipped_sovereign_template_passes() -> None:
    """The real templates/uae-sovereign/models.yaml, not a fixture — if the
    template drifts out of compliance, this is what says so."""
    result = sov.run(CONTROL, {"root": str(ROOT)})
    assert result.status == "pass", result.message
    assert "degrade ladder" in result.message


# ── Ways residency leaks ──────────────────────────────────────────────────────


def test_a_hosted_provider_fails() -> None:
    roles = {"architect": {"id": "claude", "provider": "anthropic"}}
    problems = sov._violations(roles)
    assert problems and "hosted multi-tenant" in problems[0]


def test_a_role_that_degrades_out_of_country_fails() -> None:
    """The case a live endpoint probe structurally cannot catch.

    `architect` is in-border and answers healthily. Its fallback is not. The
    probe checks the endpoint that never moves; the traffic moves on overload.
    """
    roles = {
        "architect": _ollama(degrade_to="backup"),
        "backup": {"id": "gpt-4o", "provider": "openai", "endpoint": "https://api.openai.com/v1"},
    }
    problems = sov._violations(roles)
    assert any("via degrade → backup" in p for p in problems), problems
    assert any("architect" in p for p in problems)


def test_a_self_hostable_provider_without_an_endpoint_fails() -> None:
    """`azure_openai` with no endpoint is the vendor default, which is not
    in-border by accident."""
    roles = {"architect": {"id": "gpt-4o", "provider": "azure_openai"}}
    problems = sov._violations(roles)
    assert problems and "no endpoint" in problems[0]


def test_a_dangling_degrade_target_fails() -> None:
    """Not a safe failure: the ladder ends early and the caller gets whatever
    the gateway does when it runs out of rungs."""
    roles = {"architect": _ollama(degrade_to="does_not_exist")}
    problems = sov._violations(roles)
    assert problems and "not a declared role" in problems[0]


def test_an_unrecognised_provider_fails_closed() -> None:
    """An unknown provider is not assumed in-border. A residency check that
    defaults to 'probably fine' is the failure this control exists to avoid."""
    roles = {"architect": {"id": "x", "provider": "some_new_vendor", "endpoint": "https://x"}}
    problems = sov._violations(roles)
    assert problems and "not a recognised" in problems[0]


def test_a_missing_provider_key_fails_closed() -> None:
    roles = {"architect": {"id": "x", "endpoint": "https://x"}}
    problems = sov._violations(roles)
    assert problems and "(unset)" in problems[0]


# ── Ways it must NOT false-positive ───────────────────────────────────────────


def test_an_in_border_chain_passes() -> None:
    roles = {"architect": _ollama(degrade_to="small"), "small": _ollama()}
    assert sov._violations(roles) == []


def test_a_cyclic_ladder_terminates() -> None:
    """degrade_chain stops on a repeat; the check must not hang on a registry
    that loops."""
    roles = {"a": _ollama(degrade_to="b"), "b": _ollama(degrade_to="a")}
    assert sov._violations(roles) == []


def test_a_checkout_without_the_template_is_not_applicable(tmp_path: Path) -> None:
    """A tenant that never opted into a sovereign profile has not failed a
    residency check — reporting a gap there would claim otherwise."""
    result = sov.run(CONTROL, {"root": str(tmp_path)})
    assert result.status == sov.not_applicable(CONTROL, "x").status


def test_the_runner_walks_the_same_chain_as_the_gateway() -> None:
    """The check and the runtime must not have separate opinions about where a
    degrade goes."""
    from runtime.llm_gateway import degrade_chain

    roles = {"a": _ollama(degrade_to="b"), "b": _ollama(degrade_to="c"), "c": _ollama()}
    assert degrade_chain(roles, "a") == ["a", "b", "c"]
