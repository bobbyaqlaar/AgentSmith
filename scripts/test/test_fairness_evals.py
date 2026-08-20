"""
scripts/test/test_fairness_evals.py — fairness suite loading + judge prompt shape
(no network; FIXES Data Bias & Fairness / UAE Decree-Law 34/2023).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _shared import load_script  # noqa: E402


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
    revals = load_script("run-evals")
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
    revals = load_script("run-evals")
    results = [
        {"case_id": "a", "pair_id": "p1", "fairness": 1, "score": 0.9},
        {"case_id": "b", "pair_id": "p1", "fairness": 1, "score": 0.9},
    ]
    parity = revals._pair_parity(results)
    assert parity["p1"] == 1.0


def test_pair_parity_score_is_zero_when_fairness_diverges() -> None:
    revals = load_script("run-evals")
    results = [
        {"case_id": "a", "pair_id": "p1", "fairness": 1, "score": 0.9},
        {"case_id": "b", "pair_id": "p1", "fairness": 0, "score": 0.2},
    ]
    parity = revals._pair_parity(results)
    assert parity["p1"] == 0.0


def test_resolve_fail_below_fairness_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    revals = load_script("run-evals")
    monkeypatch.setenv("FAIRNESS_FAIL_BELOW", "0.75")
    assert revals._resolve_fail_below("fairness", None) == 0.75
    assert revals._resolve_fail_below("fairness", 0.9) == 0.9  # CLI wins


def test_resolve_fail_below_fairness_defaults_to_080(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revals = load_script("run-evals")
    monkeypatch.delenv("FAIRNESS_FAIL_BELOW", raising=False)
    assert revals._resolve_fail_below("fairness", None) == 0.80


def test_load_dotenv_sets_fairness_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    revals = load_script("run-evals")
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
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(3))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"], "HTTP 400 credit balance too low"),
    )

    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 0
    assert "judge was unreachable" in capsys.readouterr().out


def test_a_partial_run_cannot_pass(monkeypatch, capsys) -> None:
    """A merge gate PASSES only when every case graded.

    The first version of this rule used `min_cases` as the quorum — 3 on a
    12-case suite — so a run could report PASS having graded five of twelve.
    Seen live on a rate-limited golden run. An average over a fraction of the
    suite is not the suite's verdict.
    """
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(4))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"],
                                   "exhausted" if case["id"] == "c3" else None,
                                   score=1.0),
    )

    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 0
    out = capsys.readouterr().out
    assert "NO VERDICT" in out
    assert "graded 3/4" in out and "a pass needs every case" in out
    assert "\u2705 PASS" not in out, "three of four graded must not report a pass"


def test_a_partial_run_can_still_fail(monkeypatch, capsys) -> None:
    """Deliberately asymmetric — a fail stands on whatever graded.

    Applied symmetrically, one flaky call alongside a real regression would
    silence the gate exactly when it matters most. Silence on a green run costs
    a re-run; silence on a red one ships the regression.
    """
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(4))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"],
                                   "exhausted" if case["id"] == "c3" else None,
                                   score=0.10),
    )

    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 1
    out = capsys.readouterr().out
    assert "\u274c FAIL" in out and "NO VERDICT" not in out
    assert "Graded:          3 of 4" in out, "the partial basis must still be stated"


def test_a_complete_run_gates_on_quality(monkeypatch, capsys) -> None:
    """The narrowing must not swallow a real failure: with every case graded,
    the score decides."""
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(4))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"], None, score=0.10),
    )

    assert revals.run_scorecard(fail_below=0.95, suite="golden") == 1
    out = capsys.readouterr().out
    assert "❌ FAIL" in out and "NO VERDICT" not in out
    assert "Graded:" not in out, "a complete run needs no partial-basis caveat"


def test_errored_cases_do_not_drag_the_average_down(monkeypatch, capsys) -> None:
    """The specific bug: 3 graded at 1.00 plus 1 errored used to average 0.75
    and fail a 0.95 gate. The errored call has no verdict to average."""
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_load_cases", lambda suite: _cases(4))
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _row(case["id"], "exhausted" if case["id"] == "c3" else None,
                                   score=1.0),
    )

    assert revals.run_scorecard(fail_below=0.95, suite="golden") == 0
    out = capsys.readouterr().out
    assert "Overall score:   1.000" in out, "should average the graded cases only"
    assert "Graded:          3 of 4" in out


# ── Verdict provenance ────────────────────────────────────────────────────────


def test_a_mixed_scorecard_blocks(monkeypatch, capsys) -> None:
    """Scores are calibrated per grader, so averaging verdicts from two models
    and comparing the result to one threshold is meaningless — and it would be
    reported to three decimal places regardless.

    Unreachable today: cost_router never substitutes a model. This is the guard
    that makes adding a fallback there fail loudly rather than quietly change
    what every stored score means.
    """
    revals = load_script("run-evals")
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
    revals = load_script("run-evals")
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


# ── Parity is gated on the WORST pair, with its own floor ────────────────────


def _pair_row(case_id, pair_id, fairness, score=1.0):
    """A fairness-suite row: `fairness` is the protected-attribute outcome that
    pair_parity compares across the pair; `score` is the judge's read of
    rationale quality, which is a different axis entirely."""
    return {
        "case_id": case_id, "pair_id": pair_id, "fairness": fairness,
        "score": score, "correctness": 1, "tool_accuracy": 1,
        "latency_ms": 0, "quality_notes": "", "judged_by": "j", "error": None,
    }


def _run_pairs(monkeypatch, rows, **kw):
    revals = load_script("run-evals")
    cases = [{"id": r["case_id"], "input": "x", "pair_id": r["pair_id"]} for r in rows]
    by_id = {r["case_id"]: r for r in rows}
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_judge_case", lambda case, *a, **k: by_id[case["id"]])
    return revals.run_scorecard(suite="fairness", **kw)


def test_one_diverging_pair_fails_however_many_clean_pairs_surround_it(
    monkeypatch, capsys
) -> None:
    """Averaging parity made the suite WEAKER the more pairs it had: with one
    pair diverging the mean is 0.750 over 2 pairs but 0.950 over 10, so a real
    protected-attribute divergence cleared a 0.95 bar purely by being
    outnumbered. Nine fair decisions do not compensate for one unfair one.
    """
    rows = []
    for i in range(9):                      # nine clean pairs
        rows += [_pair_row(f"p{i}a", f"p{i}", 1), _pair_row(f"p{i}b", f"p{i}", 1)]
    rows += [_pair_row("bad_a", "bad", 1), _pair_row("bad_b", "bad", 0)]  # one diverges

    assert _run_pairs(monkeypatch, rows, fail_below=0.80) == 1
    out = capsys.readouterr().out
    assert "Worst pair:" in out, "the gated number must be visible, not just the mean"
    assert "[bad]" in out, "the offending pair should be named"


def test_parity_floor_does_not_move_when_the_quality_bar_is_recalibrated(
    monkeypatch,
) -> None:
    """The bug this replaces: parity borrowed `fail_below`, so lowering the
    quality bar for a stricter grader silently loosened the bias control too.
    KYC Sentinel dropped fairness 0.95 -> 0.80 on 2026-08-19 for exactly that
    reason — a judge docking one rationale on formatting must not also buy
    tolerance for a rating that moved on gender.
    """
    rows = [_pair_row("a", "p", 1), _pair_row("b", "p", 0)]     # diverging pair
    assert _run_pairs(monkeypatch, rows, fail_below=0.10) == 1, (
        "a permissive quality bar must not excuse a parity divergence"
    )


def test_clean_parity_passes_even_when_rationale_quality_is_mediocre(
    monkeypatch,
) -> None:
    """The converse, and the case that actually fired in CI run 32245372194:
    parity 1.000 while the judge scored one rationale 0.33 on formatting. That
    is a quality signal, and it belongs to `fail_below` — not to the bias gate.
    """
    rows = [_pair_row("a", "p", 1, score=1.0), _pair_row("b", "p", 1, score=0.33)]
    assert _run_pairs(monkeypatch, rows, fail_below=0.60) == 0


def test_an_unparseable_parity_floor_stays_strict(monkeypatch, capsys) -> None:
    """A typo must not silently disable the bias gate — the failure direction
    matters more here than in most config parsing."""
    revals = load_script("run-evals")
    monkeypatch.setenv("FAIRNESS_PARITY_FAIL_BELOW", "one")
    assert revals._resolve_parity_fail_below() == 1.0
    assert "not a number" in capsys.readouterr().out
