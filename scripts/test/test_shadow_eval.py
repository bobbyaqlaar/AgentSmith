"""
test_shadow_eval.py — no-network regression coverage for shadow-eval.py's
sampling determinism and the shared eval_judge.py prompt shape (P1c). The
live end-to-end path (real Phoenix spans -> sample -> judge -> annotate)
was verified manually against a running Phoenix instance during
implementation; this is the CI-safe regression layer on top of that.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_shadow_eval():
    spec = importlib.util.spec_from_file_location(
        "shadow_eval", SCRIPTS_DIR / "shadow-eval.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sample_is_deterministic_across_runs():
    se = _load_shadow_eval()
    spans = [{"context": {"span_id": f"span{i:04d}"}} for i in range(500)]
    first = {s["context"]["span_id"] for s in se._sample(spans, 0.05)}
    second = {s["context"]["span_id"] for s in se._sample(spans, 0.05)}
    assert first == second


def test_sample_rate_roughly_matches_requested_fraction():
    se = _load_shadow_eval()
    spans = [{"context": {"span_id": f"span{i:05d}"}} for i in range(5000)]
    sampled = se._sample(spans, 0.05)
    fraction = len(sampled) / len(spans)
    assert 0.03 < fraction < 0.07


def test_sample_disjoint_at_zero_and_full_rate():
    se = _load_shadow_eval()
    spans = [{"context": {"span_id": f"span{i:04d}"}} for i in range(100)]
    assert se._sample(spans, 0.0) == []
    assert len(se._sample(spans, 1.0)) == len(spans)


def test_judge_prompt_includes_no_reference_marker_for_shadow_cases():
    from eval_judge import judge_prompt

    prompt = judge_prompt(
        instructions="Judge correctness.",
        historical_text="(none)",
        input_text="What is 2 + 2?",
        expected_tool="any",
        reference_output="(none — production span, judged from first principles)",
        actual_output="4",
    )
    assert "What is 2 + 2?" in prompt
    assert "4" in prompt
    assert "judged from first principles" in prompt
