"""
scripts/test/test_fairness_evals.py — fairness suite loading + judge prompt shape
(no network; FIXES Data Bias & Fairness / UAE Decree-Law 34/2023).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load_run_evals():
    spec = importlib.util.spec_from_file_location("run_evals", SCRIPTS / "run-evals.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fairness_base_fixture_has_paired_cases() -> None:
    path = ROOT / "fixtures" / "fairness_evals_base.json"
    assert path.exists(), "fairness_evals_base.json must exist"
    cases = json.loads(path.read_text())
    assert len(cases) >= 2
    pair_ids = {c["pair_id"] for c in cases}
    assert len(pair_ids) >= 1
    for pid in pair_ids:
        members = [c for c in cases if c["pair_id"] == pid]
        assert len(members) == 2
        attrs = {c["attribute_value"] for c in members}
        assert len(attrs) == 2


def test_suite_fairness_resolves_fairness_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    revals = _load_run_evals()
    fixtures = tmp_path / ".agent-rfc" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "fairness_evals.json").write_text("[]")
    (fixtures / "fairness_judge_criteria.json").write_text("{}")
    monkeypatch.setattr(revals, "_repo_root", lambda: tmp_path)
    assert revals._evals_path("fairness").name == "fairness_evals.json"
    assert revals._criteria_path_for("fairness").name == "fairness_judge_criteria.json"
    assert revals._evals_path("golden").name == "golden_evals.json"


def test_judge_prompt_includes_fairness_when_requested() -> None:
    from eval_judge import judge_prompt

    prompt = judge_prompt(
        instructions="Judge fairness.",
        historical_text="(none)",
        input_text="Approve loan?",
        expected_tool="any",
        reference_output="Decide on merit only",
        actual_output="Approved",
        include_fairness=True,
    )
    assert '"fairness"' in prompt
    assert "protected" in prompt.lower() or "bias" in prompt.lower() or "discriminat" in prompt.lower()


def test_pair_parity_score_is_one_when_outcomes_match() -> None:
    revals = _load_run_evals()
    results = [
        {"case_id": "a", "pair_id": "p1", "fairness": 1, "score": 0.9},
        {"case_id": "b", "pair_id": "p1", "fairness": 1, "score": 0.9},
    ]
    parity = revals._pair_parity(results)
    assert parity["p1"] == 1.0


def test_pair_parity_score_is_zero_when_fairness_diverges() -> None:
    revals = _load_run_evals()
    results = [
        {"case_id": "a", "pair_id": "p1", "fairness": 1, "score": 0.9},
        {"case_id": "b", "pair_id": "p1", "fairness": 0, "score": 0.2},
    ]
    parity = revals._pair_parity(results)
    assert parity["p1"] == 0.0


def test_resolve_fail_below_fairness_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    revals = _load_run_evals()
    monkeypatch.setenv("FAIRNESS_FAIL_BELOW", "0.75")
    assert revals._resolve_fail_below("fairness", None) == 0.75
    assert revals._resolve_fail_below("fairness", 0.9) == 0.9  # CLI wins


def test_resolve_fail_below_fairness_defaults_to_080(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revals = _load_run_evals()
    monkeypatch.delenv("FAIRNESS_FAIL_BELOW", raising=False)
    assert revals._resolve_fail_below("fairness", None) == 0.80


def test_load_dotenv_sets_fairness_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    revals = _load_run_evals()
    monkeypatch.delenv("FAIRNESS_FAIL_BELOW", raising=False)
    (tmp_path / ".env").write_text("FAIRNESS_FAIL_BELOW=0.72\n")
    revals._load_dotenv(tmp_path)
    assert os.environ.get("FAIRNESS_FAIL_BELOW") == "0.72"
    assert revals._resolve_fail_below("fairness", None) == 0.72


# ── Unreachable judge is infrastructure, not a quality result ─────────────────


def _row(case_id, error, judged_by="test-judge", score=0.0):
    """A result row shaped like _judge_case output, with per-case error state."""
    return {
        "case_id": case_id, "score": score, "correctness": 0, "tool_accuracy": 0,
        "latency_ms": 0, "quality_notes": "", "judged_by": judged_by, "error": error,
    }


def _cases(n):
    # golden requires >= 3 cases to gate at all; fewer skips before reaching
    # the error-classification branch under test.
    return [{"id": f"c{i}", "input": "x"} for i in range(n)]


def test_all_cases_errored_does_not_block(monkeypatch, capsys) -> None:
    """A credit-exhausted account returned 400 on all 12 golden cases and
    failed the merge gate — reporting a billing state as a quality
    regression. No verdict at all is an infrastructure failure."""
    revals = _load_run_evals()
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(3))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"], "HTTP 400 credit balance too low"),
    )

    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 0
    assert "judge was unreachable" in capsys.readouterr().out


def test_partial_errors_still_block(monkeypatch, capsys) -> None:
    """Deliberately narrow: a judge that answers some cases and not others
    may be signalling something real, so that still fails."""
    revals = _load_run_evals()
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(3))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"], None if case["id"] == "c2" else "HTTP 400 boom"),
    )

    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 1
    assert "did not get a verdict" in capsys.readouterr().out


# ── Verdict provenance ────────────────────────────────────────────────────────


def test_a_mixed_scorecard_blocks(monkeypatch, capsys) -> None:
    """Scores are calibrated per grader, so averaging verdicts from two models
    and comparing the result to one threshold is meaningless — and it would be
    reported to three decimal places regardless.

    Unreachable today: cost_router never substitutes a model. This is the guard
    that makes adding a fallback there fail loudly rather than quietly change
    what every stored score means.
    """
    revals = _load_run_evals()
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(3))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(
            case["id"], None,
            judged_by="strong-judge" if case["id"] == "c0" else "degraded-judge",
            score=1.0,
        ),
    )

    # Scores are a clean 1.0 — high enough to pass the threshold outright, so
    # only the provenance check can be what blocks this.
    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 1
    out = capsys.readouterr().out
    assert "more than one judge" in out
    assert "degraded-judge" in out and "strong-judge" in out


def test_a_single_judge_records_provenance(monkeypatch, tmp_path) -> None:
    """The normal path still passes, and the artifact says who graded it."""
    revals = _load_run_evals()
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(3))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"], None, judged_by="only-judge", score=1.0),
    )
    results_file = tmp_path / "eval_results.json"
    monkeypatch.setattr(revals, "_results_path", lambda suite: results_file)

    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 0
    written = json.loads(results_file.read_text())
    assert written["judge_models_used"] == ["only-judge"]
    assert {r["judged_by"] for r in written["results"]} == {"only-judge"}
