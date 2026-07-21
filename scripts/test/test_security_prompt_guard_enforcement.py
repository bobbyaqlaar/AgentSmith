"""
scripts/test/test_security_prompt_guard_enforcement.py — SEC-PROMPT-001
must prove ENFORCEMENT, not just detection (TestbedFeedback-2026-07-21 G9).

The runner used to call scan_prompt() only, so the control reported "Met"
regardless of whether anything was actually blocked at the gateway — a
compliance claim that could outlive the behaviour backing it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from security.registry import ControlSpec, FrameworkTags  # noqa: E402
from security.runners.prompt_guard import run as run_prompt_guard  # noqa: E402


def _control() -> ControlSpec:
    return ControlSpec(
        id="SEC-PROMPT-001",
        title="Prompt injection guard",
        status="met",
        owner="framework",
        frameworks=FrameworkTags(owasp=["LLM01"], nist=["MAP 2.6"], atlas=[], iso42001=[9]),
        runner="prompt_guard",
        check_type="unit",
        mechanism="heuristics",
    )


@pytest.mark.parametrize("mode", ["default", "strict", "block"])
def test_enforcing_modes_pass(monkeypatch, mode):
    monkeypatch.setenv("PROMPT_GUARD", mode)
    result = run_prompt_guard(_control(), {"root": REPO})
    assert result.status == "pass"
    assert "enforcing" in result.message


def test_warn_mode_is_reported_not_silently_passed(monkeypatch):
    """The observe-first tier is legitimate, but it is not enforcement —
    it must be visible (and fail --strict CI)."""
    monkeypatch.setenv("PROMPT_GUARD", "warn")
    result = run_prompt_guard(_control(), {"root": REPO})
    assert result.status == "warn"
    assert "without blocking" in result.message
    assert result.evidence["mode"] == "warn"


def test_off_is_a_failure(monkeypatch):
    monkeypatch.setenv("PROMPT_GUARD", "off")
    result = run_prompt_guard(_control(), {"root": REPO})
    assert result.status == "fail"
    assert "PROMPT_GUARD=off" in result.message


def test_unset_env_enforces(monkeypatch):
    """Secure by default: an unconfigured tenant is enforcing."""
    monkeypatch.delenv("PROMPT_GUARD", raising=False)
    assert run_prompt_guard(_control(), {"root": REPO}).status == "pass"
