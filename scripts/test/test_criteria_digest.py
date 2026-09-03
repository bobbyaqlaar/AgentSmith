"""
scripts/test/test_criteria_digest.py — a score must record the RUBRIC that
produced it, not just the judge.

THE GAP THIS CLOSES. `run-evals` stored the rubric as a static NAME
(`criteria: "default"`), while `promote-learning.py` appends to
`historical_learnings` and `eval_judge.judge_prompt` injects those into every
prompt it builds. So the rubric mutated as production failures were promoted
and the scorecard kept saying the same thing. Two runs both stamped
`criteria: "default"` could have been graded under materially different
instructions, and nothing downstream could tell.

The codebase already made this exact argument for the other input to a verdict:
`run_judge` records `judged_by` per row because "who graded this belongs with
the score, not in a single run-level field a substitution would silently
falsify." The principle was established and applied to one of the two inputs.

Raised by an outside critique of LLM-judge practice — "version your rubric like
code, and refuse to compare scores across versions" — which is the same
sentence with a different subject.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from eval_judge import criteria_digest

BASE = {
    "name": "default",
    "instructions": "Grade strictly against the reference.",
    "historical_learnings": ["prefer grounded citations"],
}


def test_digest_is_stable_and_short() -> None:
    d = criteria_digest(BASE)
    assert d == criteria_digest(dict(BASE)), "same content must hash the same"
    assert len(d) == 12 and all(c in "0123456789abcdef" for c in d)


def test_key_order_does_not_change_the_digest() -> None:
    """A reordered YAML/JSON file is not a different rubric. A digest that
    churns on cosmetic edits gets ignored within a week."""
    shuffled = {
        "historical_learnings": BASE["historical_learnings"],
        "name": BASE["name"],
        "instructions": BASE["instructions"],
    }
    assert criteria_digest(shuffled) == criteria_digest(BASE)


def test_promoting_a_learning_changes_the_digest() -> None:
    """The whole point. This is what promote-learning.py does on every
    promotion, and it changes what the judge is asked."""
    promoted = dict(BASE, historical_learnings=BASE["historical_learnings"] + ["new rule"])
    assert criteria_digest(promoted) != criteria_digest(BASE)


def test_reordering_learnings_changes_the_digest() -> None:
    """They are injected as an ordered list, so order is part of the prompt."""
    reordered = dict(BASE, historical_learnings=["b", "a"])
    assert criteria_digest(reordered) != criteria_digest(dict(BASE, historical_learnings=["a", "b"]))


def test_changing_instructions_changes_the_digest() -> None:
    assert criteria_digest(dict(BASE, instructions="Grade leniently.")) != criteria_digest(BASE)


def test_toggling_a_scoring_dimension_changes_the_digest() -> None:
    """These switch whole dimensions on and off — as material as the prose."""
    for flag in ("score_fairness", "score_hallucination", "score_adversarial"):
        assert criteria_digest(dict(BASE, **{flag: True})) != criteria_digest(BASE), flag


def test_judge_case_stamps_the_digest_on_the_verdict(monkeypatch) -> None:
    """Stamped inside judge_case, next to judged_by, so the verdict and the
    rubric that produced it are not joinable only by hoping two code paths
    agree."""
    import eval_judge

    monkeypatch.setattr(eval_judge, "run_judge", lambda prompt, model: {"score": 1.0})
    scored = eval_judge.judge_case(
        {"id": "c", "input": "in", "actual_output": "out"}, BASE, "some-judge"
    )
    assert scored["criteria_digest"] == criteria_digest(BASE)


def test_the_stored_row_carries_the_digest() -> None:
    """Guard against the field being computed and then dropped on the way to
    the artifact — which is where a provenance field usually dies."""
    src = (REPO / "scripts" / "run-evals.py").read_text(encoding="utf-8")
    assert '"criteria_digest": scored.get("criteria_digest")' in src, (
        "per-case row no longer carries criteria_digest"
    )
    assert '"criteria_digest": criteria_digest(criteria)' in src, (
        "run-level summary no longer records the rubric digest"
    )


def test_a_mixed_rubric_scorecard_is_rejected() -> None:
    """Mirrors the mixed-judge guard. Unreachable while criteria load once per
    run, which is why it exists: a future per-case or mid-run reload should
    fail loudly rather than quietly change what the average means."""
    src = (REPO / "scripts" / "run-evals.py").read_text(encoding="utf-8")
    assert "graded under more than one " in src and "rubric" in src, (
        "the mixed-rubric gate check is gone"
    )
