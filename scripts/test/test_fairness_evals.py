"""
scripts/test/test_fairness_evals.py — fairness suite loading + judge prompt shape
(no network; FIXES Data Bias & Fairness / UAE Decree-Law 34/2023).
"""

from __future__ import annotations

import importlib.util
import json
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
