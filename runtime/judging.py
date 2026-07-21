"""
runtime/judging.py — reusable judge primitives (TestbedFeedback-2026-07-21 G7).

Two checks were living in two places with no shared code:

  - **Pair parity** — `scripts/run-evals.py._pair_parity` gated fairness in
    CI, while a tenant that wanted to enforce parity per request wrote its
    own (KYC Sentinel's `judge.check_parity`).
  - **Citation grounding** — the framework only had a judge-*model* scored
    hallucination suite; a live app that wants a hard "every citation must
    be in the retrieved set" gate wrote it itself.

Promoting them here means the CI gate and the production check run the SAME
logic — the same argument that justified sharing `DEFAULT_JUDGE_MODEL` and
the Luhn validator. `run-evals.py` imports `pair_parity` from here; tenant
apps import `citations_grounded` / `outcomes_match` for per-request use.

Pure functions, no LLM, no I/O — the deterministic core beneath any
model-graded evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence


# ── Citation grounding ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class CitationCheck:
    """Result of grounding a set of citations against what was retrieved."""

    grounded: bool
    unresolved: list[str] = field(default_factory=list)
    reason: str = ""


def citations_grounded(
    citations: Sequence[str],
    retrieved_ids: Iterable[str],
    *,
    require_at_least_one: bool = True,
) -> CitationCheck:
    """True when every citation resolves to a retrieved id.

    An unresolved citation is a hallucinated source — a claim attributed to
    a document the system never actually retrieved. `require_at_least_one`
    also flags a rationale that cites nothing at all (an ungrounded
    conclusion), which is the posture a decision-path app wants; set it
    False if empty citations are legitimately allowed.
    """
    retrieved = set(retrieved_ids)
    unresolved = [c for c in citations if c not in retrieved]
    missing = require_at_least_one and not list(citations)
    if unresolved:
        return CitationCheck(False, unresolved, f"citations not in retrieved set: {unresolved}")
    if missing:
        return CitationCheck(False, [], "no citations provided for a claim requiring grounding")
    return CitationCheck(True, [], "")


# ── Pair parity (fairness) ───────────────────────────────────────────────────


def outcomes_match(a: Any, b: Any) -> bool:
    """The atom of a parity check: two paired outcomes must be equal.

    Deliberately identity of the outcome value (a rating string, a decision
    bit, an APPROVE/DENY label) — a protected attribute must not move it.
    """
    return a == b


def pair_parity(results: Sequence[dict], *, outcome_key: str = "fairness") -> dict[str, float]:
    """Per-pair parity scores keyed by `pair_id`.

    1.0 when both members of a pair share the same `outcome_key` value, else
    0.0. Pairs with fewer than two scored members are omitted (nothing to
    compare). This is the exact contract `scripts/run-evals.py` gated
    fairness on before it was promoted here — `outcome_key` defaults to
    `fairness` for that caller; a tenant scoring on ratings passes
    `outcome_key="rating"`.
    """
    by_pair: dict[str, list[dict]] = {}
    for r in results:
        pid = r.get("pair_id")
        if pid:
            by_pair.setdefault(pid, []).append(r)

    out: dict[str, float] = {}
    for pid, members in by_pair.items():
        if len(members) < 2:
            continue
        a, b = members[0].get(outcome_key), members[1].get(outcome_key)
        # Preserve run-evals' historical normalization: the fairness bit is
        # coerced to int (a missing/None value counts as 0) before comparing.
        if outcome_key == "fairness":
            a, b = int(a or 0), int(b or 0)
        out[pid] = 1.0 if outcomes_match(a, b) else 0.0
    return out


def parity_violation(a: Any, b: Any, *, attribute: str = "protected attribute") -> Optional[str]:
    """Human-readable reason when two paired outcomes diverge, else None.

    The per-request companion to `pair_parity`: a tenant judge calls this on
    the two ratings it just produced for a swapped-attribute pair.
    """
    if outcomes_match(a, b):
        return None
    return (
        f"parity violation: identical inputs differing only in {attribute} "
        f"produced {a!r} vs {b!r}"
    )
