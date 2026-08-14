"""
scripts/test/test_eval_pacing.py — EVAL_RPM paces judge calls.

Why this exists: a free-tier judge key with a per-minute cap refuses a burst of
judge calls faster than cost_router's 4-attempt retry budget can absorb. Every
case then carries an error, and `run_scorecard` reports "judge was unreachable"
and returns 0 — deliberately, because no verdict at all is an infrastructure
failure rather than a quality regression (see test_fairness_evals.py).

The consequence is the part worth guarding: an unpaced run against a free tier
does not fail. It silently never grades, which reads as a stuck eval rather
than a broken one, and a merge gate that never grades is a merge gate that is
not there.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _shared import RateLimiter, load_script, rate_limiter_from_env  # noqa: E402


def _row(case_id: str) -> dict:
    return {
        "case_id": case_id, "score": 1.0, "correctness": 1, "tool_accuracy": 1,
        "latency_ms": 0, "quality_notes": "", "judged_by": "only-judge", "error": None,
    }


# ── The limiter itself ────────────────────────────────────────────────────────


def test_limiter_spaces_calls_by_the_configured_interval() -> None:
    limiter = RateLimiter(rpm=240)          # 4/sec → 0.25s apart
    start = time.monotonic()
    for _ in range(3):
        limiter.wait()
    elapsed = time.monotonic() - start
    # Two gaps between three calls; the first is free.
    assert elapsed >= 0.45, f"expected ≥0.45s of pacing, got {elapsed:.3f}s"


def test_the_first_call_is_not_delayed() -> None:
    """Pacing must not add latency before the first request — a one-case run
    should not wait for a quota it has not used."""
    limiter = RateLimiter(rpm=6)            # 10s apart, if it applied
    start = time.monotonic()
    limiter.wait()
    assert time.monotonic() - start < 0.1


@pytest.mark.parametrize("rpm", [0, 0.0, -1])
def test_a_non_positive_rate_is_a_no_op_object_not_none(rpm: float) -> None:
    """Callers have no branch at the call site, so 'disabled' must still be a
    usable limiter rather than None."""
    limiter = RateLimiter(rpm=rpm)
    assert limiter.enabled is False
    assert limiter.wait() == 0.0


def test_unset_env_means_no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The historical behaviour is the default: pacing costs wall-clock and is
    only worth it on a capped key."""
    monkeypatch.delenv("EVAL_RPM", raising=False)
    assert rate_limiter_from_env().enabled is False


def test_an_unparseable_rate_warns_and_does_not_pace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A typo must not silently throttle a paid run to a crawl, nor crash a
    suite that was about to grade correctly."""
    monkeypatch.setenv("EVAL_RPM", "ten")
    limiter = rate_limiter_from_env()
    assert limiter.enabled is False
    assert "not a number" in capsys.readouterr().out


# ── Wired into the judged loop ────────────────────────────────────────────────


def test_the_judged_loop_is_paced_when_eval_rpm_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x"} for i in range(3)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_judge_case", lambda case, *a, **k: _row(case["id"]))
    monkeypatch.setenv("EVAL_RPM", "240")   # 0.25s apart → ≥0.5s for 3 cases

    start = time.monotonic()
    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 0
    assert time.monotonic() - start >= 0.45


def test_the_judged_loop_is_not_paced_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x"} for i in range(3)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_judge_case", lambda case, *a, **k: _row(case["id"]))
    monkeypatch.delenv("EVAL_RPM", raising=False)

    start = time.monotonic()
    assert revals.run_scorecard(fail_below=0.8, suite="golden") == 0
    assert time.monotonic() - start < 0.5


# ── An unreachable judge must not READ as a quality failure ───────────────────


def test_an_all_errored_run_says_no_verdict_rather_than_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The gate already exits 0 when no case got a verdict. The banner used to
    print "❌ FAIL" a few lines above the message saying it does not block —
    a direct contradiction, and a reader scanning CI output stops at the ❌.

    Seen live on a rate-limited fairness run that had failed nothing.
    """
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x", "pair_id": "p1"} for i in range(4)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_judge_case", lambda case, *a, **k: {
        "case_id": case["id"], "score": 0.0, "correctness": 0, "tool_accuracy": 0,
        "latency_ms": 0, "quality_notes": "", "judged_by": "j", "fairness": 1,
        "pair_id": "p1", "error": "Provider exhausted for model 'x'",
    })

    assert revals.run_scorecard(fail_below=0.95, suite="fairness") == 0
    out = capsys.readouterr().out
    assert "NO VERDICT" in out
    assert "❌ FAIL" not in out, "an infrastructure state must not read as a failed gate"
    assert "was unreachable" in out


def test_a_genuine_quality_failure_still_says_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The narrowing must not swallow a real one: verdicts that came back and
    fell short still fail, and still say so."""
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x", "pair_id": "p1"} for i in range(4)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_judge_case", lambda case, *a, **k: {
        "case_id": case["id"], "score": 0.10, "correctness": 0, "tool_accuracy": 1,
        "latency_ms": 0, "quality_notes": "", "judged_by": "j", "fairness": 1,
        "pair_id": "p1", "error": None,
    })

    assert revals.run_scorecard(fail_below=0.95, suite="fairness") == 1
    out = capsys.readouterr().out
    assert "❌ FAIL" in out and "NO VERDICT" not in out


# ── A judged case has no pass/fail of its own ─────────────────────────────────


def test_a_case_below_the_bar_is_not_marked_failed_on_a_passing_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`fail_below` gates the suite AVERAGE, so a single case under it has not
    failed anything. Printing ❌ beside it made a passing run look broken —
    golden's kyc_005 sits at 0.90 and drew a red cross on a run that passed at
    0.992. Same report-contradicts-verdict problem as the NO VERDICT banner.
    """
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x"} for i in range(4)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: {**_row(case["id"]),
                               "score": 0.90 if case["id"] == "c1" else 1.0},
    )

    assert revals.run_scorecard(fail_below=0.95, suite="golden") == 0
    out = capsys.readouterr().out
    assert "✅ PASS" in out, "0.975 average clears 0.95"
    assert "❌" not in out, "no case failed; nothing should carry a red cross"
    assert "below the 0.95 suite bar" in out, "the low case must still be visible"


def test_an_errored_case_is_marked_no_verdict_not_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """What IS knowable per case is whether it got a verdict at all."""
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x"} for i in range(4)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: {**_row(case["id"]),
                               "error": "exhausted" if case["id"] == "c3" else None},
    )

    revals.run_scorecard(fail_below=0.95, suite="golden")
    out = capsys.readouterr().out
    assert "⏭️ " in out, "the errored case should read as no-verdict"
    assert "❌" not in out


def test_deterministic_suites_keep_their_real_per_case_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """adversarial and rag_poison score each case against its OWN expectation,
    so ❌ there is a genuine per-case result and must survive this change."""
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_load_cases", lambda suite: [
        {"id": "a1", "expect": "quarantine", "document": "benign", "pair_id": "p"},
        {"id": "a2", "expect": "quarantine", "document": "benign", "pair_id": "p"},
        {"id": "a3", "expect": "quarantine", "document": "benign", "pair_id": "p"},
    ])
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})

    revals.run_scorecard(fail_below=0.95, suite="rag_poison")
    assert "❌" in capsys.readouterr().out, "a genuinely missed case must still show ❌"
