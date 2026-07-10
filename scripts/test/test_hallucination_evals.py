from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def _load_run_evals():
    spec = importlib.util.spec_from_file_location("run_evals", SCRIPTS / "run-evals.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_hallucination_flag_rate_empty():
    revals = _load_run_evals()
    assert revals.hallucination_flag_rate([]) == 0.0


def test_hallucination_flag_rate_threshold():
    revals = _load_run_evals()
    rows = [
        {"hallucination": 0.0},
        {"hallucination": 0.6},  # flagged (>= 0.5)
        {"hallucination": 0.4},
        {"score": 1.0},  # no hallucination key — skip
    ]
    # 1 flagged / 3 scored = ~0.333
    assert abs(revals.hallucination_flag_rate(rows) - (1 / 3)) < 1e-9


def test_resolve_hallucination_fail_above_cli_wins(monkeypatch: pytest.MonkeyPatch):
    revals = _load_run_evals()
    monkeypatch.setenv("HALLUCINATION_FAIL_ABOVE", "0.10")
    assert revals._resolve_hallucination_fail_above(0.02) == 0.02


def test_resolve_hallucination_fail_above_env(monkeypatch: pytest.MonkeyPatch):
    revals = _load_run_evals()
    monkeypatch.setenv("HALLUCINATION_FAIL_ABOVE", "0.08")
    assert revals._resolve_hallucination_fail_above(None) == 0.08


def test_resolve_hallucination_fail_above_default(monkeypatch: pytest.MonkeyPatch):
    revals = _load_run_evals()
    monkeypatch.delenv("HALLUCINATION_FAIL_ABOVE", raising=False)
    assert revals._resolve_hallucination_fail_above(None) == 0.05


def test_judge_prompt_includes_hallucination_field():
    from eval_judge import judge_prompt

    p = judge_prompt(
        instructions="x",
        historical_text="(none)",
        input_text="q",
        expected_tool="any",
        reference_output="r",
        actual_output="a",
        include_hallucination=True,
    )
    assert '"hallucination"' in p
    assert "not supported by the input" in p.lower() or "unsupported" in p.lower()
