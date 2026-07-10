from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

REQUIRED_HALLUCINATION_CASE_KEYS = (
    "id",
    "input",
    "reference_output",
    "expected_tool",
    "actual_output",
    "score_hallucination",
)


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


def test_hallucination_base_fixture_has_grounded_cases() -> None:
    path = ROOT / "fixtures" / "hallucination_evals_base.json"
    assert path.exists(), "hallucination_evals_base.json must exist"
    cases = json.loads(path.read_text())
    assert len(cases) == 4
    for case in cases:
        for key in REQUIRED_HALLUCINATION_CASE_KEYS:
            assert key in case


def test_load_dotenv_sets_hallucination_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revals = _load_run_evals()
    monkeypatch.delenv("HALLUCINATION_FAIL_ABOVE", raising=False)
    (tmp_path / ".env").write_text("HALLUCINATION_FAIL_ABOVE=0.07\n")
    revals._load_dotenv(tmp_path)
    assert os.environ.get("HALLUCINATION_FAIL_ABOVE") == "0.07"
    assert revals._resolve_hallucination_fail_above(None) == 0.07
