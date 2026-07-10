"""
run-evals.py — Evaluation scorecard (golden + fairness suites).

1. Loads cases from .agent-rfc/fixtures/ (golden_evals.json or fairness_evals.json)
2. Loads matching judge criteria
3. Runs each case through the configured LLM judge (AGENT_JUDGE_MODEL)
4. Scores: correctness, tool_accuracy, latency; fairness suite also scores fairness
   and pair parity across protected-attribute pairs
5. Exits non-zero if score < --fail-below threshold

Golden dataset lifecycle:
  < 3 cases   → skip gracefully (no gate, prints notice)
  1-9 cases   → baseline run
  10+ cases   → meaningful signal, blocks low-quality PRs
  50+ cases   → production-calibrated

Usage:
    python3 scripts/run-evals.py
    python3 scripts/run-evals.py --fail-below 0.85
    python3 scripts/run-evals.py --suite fairness --fail-below 0.80
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

from _shared import _repo_root  # noqa: E402


def _evals_path(suite: str = "golden") -> Path:
    name = "fairness_evals.json" if suite == "fairness" else "golden_evals.json"
    return _repo_root() / ".agent-rfc" / "fixtures" / name


def _criteria_path_for(suite: str = "golden") -> Path:
    name = (
        "fairness_judge_criteria.json"
        if suite == "fairness"
        else "custom_judge_criteria.json"
    )
    return _repo_root() / ".agent-rfc" / "fixtures" / name


def _golden_path() -> Path:
    return _evals_path("golden")


def _criteria_path() -> Path:
    return _criteria_path_for("golden")


def _results_path(suite: str = "golden") -> Path:
    name = "fairness_eval_results.json" if suite == "fairness" else "eval_results.json"
    return _repo_root() / ".agent-rfc" / "fixtures" / name


# ── Load fixtures ─────────────────────────────────────────────────────────────


def _load_cases(suite: str = "golden") -> list[dict]:
    path = _evals_path(suite)
    if not path.exists():
        # Fairness: fall back to framework base seed if tenant file absent
        if suite == "fairness":
            base = (
                Path(__file__).resolve().parent.parent
                / "fixtures"
                / "fairness_evals_base.json"
            )
            if base.exists():
                with base.open() as fh:
                    return json.load(fh)
        return []
    with path.open() as fh:
        return json.load(fh)


def _load_golden_cases() -> list[dict]:
    return _load_cases("golden")


def _load_criteria(suite: str = "golden") -> dict:
    path = _criteria_path_for(suite)
    if not path.exists():
        if suite == "fairness":
            base = (
                Path(__file__).resolve().parent.parent
                / "fixtures"
                / "fairness_judge_criteria_base.json"
            )
            if base.exists():
                with base.open() as fh:
                    return json.load(fh)
            return {
                "name": "Fairness",
                "score_fairness": True,
                "instructions": "Judge fairness and bias.",
            }
        return {
            "name": "Default",
            "instructions": "Judge correctness, safety, and quality.",
        }
    with path.open() as fh:
        return json.load(fh)


def _pair_parity(results: list[dict]) -> dict[str, float]:
    """
    For each pair_id, 1.0 if both members have the same fairness bit (both 1
    or both 0), else 0.0. Pairs with fewer than 2 scored members are omitted.
    """
    by_pair: dict[str, list[dict]] = {}
    for r in results:
        pid = r.get("pair_id")
        if not pid:
            continue
        by_pair.setdefault(pid, []).append(r)

    out: dict[str, float] = {}
    for pid, members in by_pair.items():
        if len(members) < 2:
            continue
        bits = [int(m.get("fairness", 0) or 0) for m in members[:2]]
        out[pid] = 1.0 if bits[0] == bits[1] else 0.0
    return out


# ── Judge invocation ──────────────────────────────────────────────────────────


def _judge_case(
    case: dict,
    criteria: dict,
    judge_model: str,
    project_response: Optional[str] = None,
) -> dict:
    """
    Ask the judge model to score one case.

    If project_response is None, the agent pipeline is invoked first to
    generate a response, then the judge scores it.
    """
    from eval_judge import judge_case as _shared_judge_case

    start = time.monotonic()

    if project_response is None:
        try:
            from local_agent_stack import run_pipeline

            result = run_pipeline(task=case["input"])
            project_response = result.get("code", "") or result.get("validation", "")
        except Exception as exc:
            project_response = f"PIPELINE_ERROR: {exc}"

    elapsed_ms = int((time.monotonic() - start) * 1000)

    scored = _shared_judge_case(case, criteria, judge_model, project_response)

    row = {
        "case_id": case.get("id", "unknown"),
        "input": case["input"][:120],
        "expected_tool": case.get("expected_tool", "any"),
        "latency_ms": elapsed_ms,
        "correctness": scored.get("correctness", 0),
        "tool_accuracy": scored.get("tool_accuracy", 0),
        "score": float(scored.get("score", 0.0)),
        "quality_notes": scored.get("quality_notes", ""),
        "error": scored.get("error"),
    }
    if "fairness" in scored:
        row["fairness"] = scored.get("fairness", 0)
    if case.get("pair_id"):
        row["pair_id"] = case["pair_id"]
        row["protected_attribute"] = case.get("protected_attribute")
        row["attribute_value"] = case.get("attribute_value")
    return row


# ── Scorecard ─────────────────────────────────────────────────────────────────


def run_scorecard(fail_below: float = 0.80, suite: str = "golden") -> int:
    """
    Run all cases for the suite and print scorecard.
    Returns exit code: 0 = pass, 1 = fail, 2 = skipped.
    """
    if suite not in {"golden", "fairness"}:
        print(f"Unknown suite {suite!r}; use golden or fairness", file=sys.stderr)
        return 1

    cases = _load_cases(suite)
    criteria = _load_criteria(suite)
    judge = os.environ.get("AGENT_JUDGE_MODEL", "claude-sonnet-4-6")
    project = _repo_root().name
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"🎯 AgentSmith Eval [{suite}] — {project} @ {ts}")
    print(f"   Judge model:  {judge}")
    print(f"   Criteria:     {criteria.get('name', 'default')}")
    print(f"   Cases loaded: {len(cases)}")

    min_cases = 2 if suite == "fairness" else 3
    if len(cases) < min_cases:
        print(
            f"   ⚠️  Only {len(cases)} {suite} case(s) found. "
            f"Need ≥{min_cases} to gate. Skipping eval run.\n"
            f"   Add cases to {_evals_path(suite)} or copy from "
            f"fixtures/{'fairness_evals_base.json' if suite == 'fairness' else 'golden_evals_base.json'}."
        )
        return 2

    results = []
    for i, case in enumerate(cases, 1):
        print(
            f"   [{i}/{len(cases)}] {case.get('id', 'case')} ...", end=" ", flush=True
        )
        r = _judge_case(case, criteria, judge)
        results.append(r)
        status = "✅" if r["score"] >= fail_below else "❌"
        fair_bit = f" fairness={r['fairness']}" if "fairness" in r else ""
        print(f"{status} score={r['score']:.2f}{fair_bit} latency={r['latency_ms']}ms")

    avg_score = sum(r["score"] for r in results) / len(results)
    avg_correctness = sum(r["correctness"] for r in results) / len(results)
    avg_tool_acc = sum(r["tool_accuracy"] for r in results) / len(results)
    avg_latency_ms = sum(r["latency_ms"] for r in results) / len(results)
    fairness_vals = [r["fairness"] for r in results if "fairness" in r]
    avg_fairness = (
        sum(fairness_vals) / len(fairness_vals) if fairness_vals else None
    )
    parity = _pair_parity(results) if suite == "fairness" else {}
    avg_parity = sum(parity.values()) / len(parity) if parity else None
    passed = avg_score >= fail_below
    if suite == "fairness" and avg_parity is not None:
        # Pair parity must also clear the threshold for fairness suite
        passed = passed and avg_parity >= fail_below

    print("")
    print("─────────────────────────────────────────────")
    print(f"  Overall score:   {avg_score:.3f}  {'✅ PASS' if passed else '❌ FAIL'}")
    print(f"  Correctness:     {avg_correctness:.3f}")
    print(f"  Tool accuracy:   {avg_tool_acc:.3f}")
    if avg_fairness is not None:
        print(f"  Fairness:        {avg_fairness:.3f}")
    if avg_parity is not None:
        print(f"  Pair parity:     {avg_parity:.3f}  ({len(parity)} pairs)")
    print(f"  Avg latency:     {avg_latency_ms:.0f}ms")
    print(f"  Threshold:       {fail_below:.2f}")
    print("─────────────────────────────────────────────")

    if not passed:
        failing = [r for r in results if r["score"] < fail_below]
        print(f"\n  Failing cases ({len(failing)}):")
        for r in failing:
            print(
                f"    • [{r['case_id']}] score={r['score']:.2f}: {r['quality_notes']}"
            )
        if parity:
            bad_pairs = [pid for pid, v in parity.items() if v < fail_below]
            if bad_pairs:
                print(f"\n  Failing pairs ({len(bad_pairs)}): {', '.join(bad_pairs)}")

    output = {
        "timestamp": ts,
        "suite": suite,
        "project": project,
        "judge_model": judge,
        "criteria": criteria.get("name", "default"),
        "total_cases": len(cases),
        "avg_score": avg_score,
        "avg_correctness": avg_correctness,
        "avg_tool_accuracy": avg_tool_acc,
        "avg_fairness": avg_fairness,
        "pair_parity": parity,
        "avg_pair_parity": avg_parity,
        "avg_latency_ms": avg_latency_ms,
        "threshold": fail_below,
        "passed": passed,
        "results": results,
    }
    results_path = _results_path(suite)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("w") as fh:
        json.dump(output, fh, indent=2)
    try:
        rel = results_path.relative_to(_repo_root())
    except ValueError:
        rel = results_path
    print(f"\n  Results saved → {rel}")

    try:
        from notifier import notify_eval_result

        notify_eval_result(avg_score, fail_below, project=project)
    except Exception:  # fail-open: desktop notification must not affect pass/fail
        pass

    return 0 if passed else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AgentSmith eval scorecard")
    parser.add_argument(
        "--fail-below",
        type=float,
        default=0.80,
        metavar="SCORE",
        help="Exit non-zero if average score < SCORE (default: 0.80)",
    )
    parser.add_argument(
        "--suite",
        choices=("golden", "fairness"),
        default="golden",
        help="Eval suite: golden (default) or fairness (paired bias audits)",
    )
    args = parser.parse_args()
    sys.exit(run_scorecard(fail_below=args.fail_below, suite=args.suite))
