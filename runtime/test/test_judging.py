"""
runtime/test/test_judging.py — shared judge primitives (TestbedFeedback G7).

These pin the exact contracts that the CI eval gate (scripts/run-evals.py)
and any tenant's per-request judge both rely on, so promoting the logic
here cannot silently change either one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime.judging import (  # noqa: E402
    CitationCheck,
    citations_grounded,
    outcomes_match,
    pair_parity,
    parity_violation,
)


# ── citation grounding ───────────────────────────────────────────────────────


def test_all_citations_resolve():
    r = citations_grounded(["p-1", "p-2"], {"p-1", "p-2", "p-3"})
    assert r == CitationCheck(True, [], "")


def test_unresolved_citation_flagged():
    r = citations_grounded(["p-1", "ghost"], {"p-1"})
    assert not r.grounded and r.unresolved == ["ghost"]
    assert "not in retrieved set" in r.reason


def test_empty_citations_flagged_by_default():
    assert not citations_grounded([], {"p-1"}).grounded


def test_empty_citations_allowed_when_opted_out():
    assert citations_grounded([], {"p-1"}, require_at_least_one=False).grounded


# ── pair parity (CI shape) ───────────────────────────────────────────────────


def test_pair_parity_matches_and_mismatches():
    results = [
        {"pair_id": "A", "fairness": 1},
        {"pair_id": "A", "fairness": 1},
        {"pair_id": "B", "fairness": 1},
        {"pair_id": "B", "fairness": 0},
    ]
    assert pair_parity(results) == {"A": 1.0, "B": 0.0}


def test_pair_parity_omits_singletons_and_unpaired():
    results = [
        {"pair_id": "solo", "fairness": 1},
        {"fairness": 1},  # no pair_id
    ]
    assert pair_parity(results) == {}


def test_pair_parity_coerces_missing_fairness_bit_to_zero():
    """Preserves run-evals' historical normalization: a missing/None fairness
    value counts as 0, so two unscored members are 'equal' (both 0)."""
    results = [{"pair_id": "A", "fairness": None}, {"pair_id": "A"}]
    assert pair_parity(results) == {"A": 1.0}


def test_pair_parity_custom_outcome_key():
    results = [
        {"pair_id": "A", "rating": "LOW"},
        {"pair_id": "A", "rating": "LOW"},
        {"pair_id": "B", "rating": "LOW"},
        {"pair_id": "B", "rating": "HIGH"},
    ]
    assert pair_parity(results, outcome_key="rating") == {"A": 1.0, "B": 0.0}


# ── parity_violation (per-request shape) ─────────────────────────────────────


def test_parity_violation_none_when_equal():
    assert parity_violation("LOW", "LOW") is None
    assert outcomes_match("LOW", "LOW")


def test_parity_violation_reports_the_divergence():
    msg = parity_violation("LOW", "HIGH", attribute="nationality")
    assert msg and "nationality" in msg and "'LOW'" in msg and "'HIGH'" in msg


def test_run_evals_delegates_to_the_shared_function():
    """The CI gate must call the promoted primitive, not a private copy —
    otherwise G7's 'same logic' guarantee is hollow."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_evals", Path(__file__).resolve().parents[2] / "scripts" / "run-evals.py"
    )
    run_evals = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_evals)

    results = [{"pair_id": "A", "fairness": 1}, {"pair_id": "A", "fairness": 0}]
    assert run_evals._pair_parity(results) == pair_parity(results) == {"A": 0.0}
