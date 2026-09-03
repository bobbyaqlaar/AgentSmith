"""
scripts/test/test_retired_judge_fails_loudly.py — a WITHDRAWN judge model must
fail the gate; an exhausted quota must not.

THE FAILURE THIS EXISTS FOR. Groq retired its entire Llama family on
2026-08-17 and `llama-3.3-70b-versatile` began returning HTTP 404
model_not_found on every call. Every judged suite reported
`NO VERDICT (judge unreachable)` and exited **0**, so CI stayed green while
grading nothing for days.

Exiting 0 there was deliberate and is still right for the case it was written
for: an exhausted quota is infrastructure weather, and blocking merges on it
reports a billing problem as a quality regression. The mistake was lumping a
withdrawn model in with it. They are opposite facts:

    quota exhausted    clears by itself overnight        -> green, annotated
    model withdrawn    never clears; models.yaml is wrong -> RED

Reported identically, the second is indistinguishable from the first, and the
run's own advice pointed at the quota console. A repo can sit pointing at a
dead grader indefinitely, every run green and ungraded.

Driven through `run_scorecard` with a stubbed judge rather than a live call:
the real thing costs judge quota, and the registry deliberately ignores
`AGENT_JUDGE_MODEL` (an ambient variable must not be able to regrade a repo),
so there is no cheap way to point a real run at a dead model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from _shared import load_script

GONE = (
    "LLM call failed [forced / llama-3.3-70b-versatile]: HTTP 404 from "
    "https://api.groq.com/openai/v1/chat/completions: "
    '{"error": {"message": "The model `llama-3.3-70b-versatile` does not exist", '
    '"type": "invalid_request_error", "code": "model_not_found"}}'
)
QUOTA = (
    "LLM call failed [forced / gemini-3-flash-preview]: HTTP 429 ... "
    "RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
)


def _row(case_id: str, error: str | None) -> dict:
    return {
        "case_id": case_id, "score": 0.0, "correctness": 0, "tool_accuracy": 0,
        "latency_ms": 0, "quality_notes": "", "judged_by": "j",
        "criteria_digest": "abc123abc123", "error": error,
    }


def _run(monkeypatch, error: str):
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x"} for i in range(4)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_write_results_to_disk", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(
        revals, "_judge_case", lambda case, *a, **k: _row(case["id"], error)
    )
    return revals.run_scorecard(fail_below=0.95, suite="golden")


def test_classifier_separates_the_two(monkeypatch) -> None:
    """Guard the guard. If `is_model_gone` ever stops recognising a real
    provider message, both tests below pass by agreeing on the wrong answer."""
    from runtime.provider_dispatch import is_model_gone, is_provider_exhausted

    assert is_model_gone(GONE) is True
    assert is_model_gone(QUOTA) is False
    # Neither implies the other — a 404 is not exhaustion, which is why a
    # withdrawn model fell into the generic bucket in the first place.
    assert is_provider_exhausted(RuntimeError(GONE)) is False
    assert is_provider_exhausted(RuntimeError(QUOTA)) is True


def test_a_withdrawn_model_fails_the_gate(monkeypatch, capsys) -> None:
    code = _run(monkeypatch, GONE)
    out = capsys.readouterr().out
    assert code == 1, "a withdrawn judge model must go RED, not green-with-no-verdict"
    assert "configured judge model is gone" in out
    assert "no later run will clear it" in out
    # Must not send the reader to the quota console.
    assert "daily request quota" not in out


def test_an_exhausted_quota_still_does_not_block(monkeypatch, capsys) -> None:
    """The behaviour the original design got right, pinned so the change above
    cannot quietly turn every infrastructure hiccup into a red build."""
    code = _run(monkeypatch, QUOTA)
    out = capsys.readouterr().out
    assert code == 0, "an exhausted quota is infrastructure, not a quality result"
    assert "does not block" in out
    assert "configured judge model is gone" not in out


@pytest.mark.parametrize("level,error", [("error", GONE), ("warning", QUOTA)])
def test_the_annotation_level_matches_the_verdict(monkeypatch, capsys, level, error) -> None:
    """An annotation reading `warning` beside a red check is the report
    disagreeing with the result."""
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    _run(monkeypatch, error)
    out = capsys.readouterr().out
    assert f"::{level} title=" in out, out[-400:]
