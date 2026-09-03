from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from _shared import load_script

REQUIRED_HALLUCINATION_CASE_KEYS = (
    "id",
    "input",
    "reference_output",
    "expected_tool",
    "actual_output",
    "score_hallucination",
)


def test_hallucination_flag_rate_empty():
    """No rows means nothing was measured, which is NOT a clean rate.

    This test previously asserted 0.0 and so locked the defect in place: zero
    flagged out of zero measured printed as "Hallucination: 0.000", the same
    reading a genuinely clean suite produces. A passing test around a wrong
    contract is why the code review that hunted duplication and dead code did
    not find this — nothing looked broken.
    """
    revals = load_script("run-evals")
    assert revals.hallucination_flag_rate([]) is None


def test_hallucination_flag_rate_threshold():
    revals = load_script("run-evals")
    rows = [
        {"hallucination": 0.0},
        {"hallucination": 0.6},  # flagged (>= 0.5)
        {"hallucination": 0.4},
        {"score": 1.0},  # no hallucination key — skip
    ]
    # 1 flagged / 3 scored = ~0.333
    assert abs(revals.hallucination_flag_rate(rows) - (1 / 3)) < 1e-9


def test_resolve_hallucination_fail_above_cli_wins(monkeypatch: pytest.MonkeyPatch):
    revals = load_script("run-evals")
    monkeypatch.setenv("HALLUCINATION_FAIL_ABOVE", "0.10")
    assert revals._resolve_hallucination_fail_above(0.02) == 0.02


def test_resolve_hallucination_fail_above_env(monkeypatch: pytest.MonkeyPatch):
    revals = load_script("run-evals")
    monkeypatch.setenv("HALLUCINATION_FAIL_ABOVE", "0.08")
    assert revals._resolve_hallucination_fail_above(None) == 0.08


def test_resolve_hallucination_fail_above_default(monkeypatch: pytest.MonkeyPatch):
    revals = load_script("run-evals")
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
    for case in cases:
        for key in REQUIRED_HALLUCINATION_CASE_KEYS:
            assert key in case
    # Asserting a COUNT here just tripped every time a case was added, which
    # trains you to bump the number rather than ask what changed. The properties
    # that matter are that clean cases exist to measure false positives, and
    # that at least one planted case exists to prove the suite can detect
    # anything at all.
    assert any(not c.get("expect_hallucination") for c in cases), "no clean cases"
    assert any(c.get("expect_hallucination") for c in cases), (
        "base fixture has no positive control — a suite of only-clean cases can "
        "score a perfect flagged-claim rate while detecting nothing"
    )


def test_hallucination_suite_paths_use_agent_rfc_fixtures() -> None:
    revals = load_script("run-evals")
    fixtures = ROOT / ".agent-rfc" / "fixtures"
    assert revals._evals_path("hallucination") == fixtures / "hallucination_evals.json"
    assert (
        revals._criteria_path_for("hallucination")
        == fixtures / "hallucination_judge_criteria.json"
    )
    assert (
        revals._results_path("hallucination")
        == fixtures / "hallucination_eval_results.json"
    )


def test_load_hallucination_cases_falls_back_to_base_fixture() -> None:
    revals = load_script("run-evals")
    cases = revals._load_cases("hallucination")
    assert cases, "fallback returned nothing"
    assert all(case["id"].startswith("halluc_") for case in cases)
    assert all(case.get("score_hallucination") is True for case in cases)


def test_run_scorecard_fails_when_hallucination_rate_exceeds_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revals = load_script("run-evals")
    cases = [
        {"id": "h1", "input": "a", "actual_output": "a"},
        {"id": "h2", "input": "b", "actual_output": "b"},
        {"id": "h3", "input": "c", "actual_output": "c"},
    ]
    verdicts = iter([0.0, 0.6, 1.0])

    def fake_judge_case(case: dict, criteria: dict, judge: str) -> dict:
        return {
            "case_id": case["id"],
            "input": case["input"],
            "expected_tool": "any",
            "latency_ms": 0,
            "correctness": 1,
            "tool_accuracy": 1,
            "score": 1.0,
            "quality_notes": "",
            "error": None,
            "hallucination": next(verdicts),
        }

    results_path = tmp_path / "hallucination_eval_results.json"
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(
        revals,
        "_load_criteria",
        lambda suite: {"name": "Hallucination", "score_hallucination": True},
    )
    monkeypatch.setattr(revals, "_judge_case", fake_judge_case)
    monkeypatch.setattr(revals, "_results_path", lambda suite: results_path)

    assert (
        revals.run_scorecard(
            fail_below=0.8,
            suite="hallucination",
            hallucination_fail_above=0.5,
        )
        == 1
    )
    output = json.loads(results_path.read_text())
    assert output["passed"] is False
    assert output["hallucination_flag_rate"] == pytest.approx(2 / 3)


def test_load_dotenv_sets_hallucination_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    revals = load_script("run-evals")
    monkeypatch.delenv("HALLUCINATION_FAIL_ABOVE", raising=False)
    (tmp_path / ".env").write_text("HALLUCINATION_FAIL_ABOVE=0.07\n")
    revals._load_dotenv(tmp_path)
    assert os.environ.get("HALLUCINATION_FAIL_ABOVE") == "0.07"
    assert revals._resolve_hallucination_fail_above(None) == 0.07


# ── The judge must be given the documents it is asked to check against ───────


def test_retrieved_context_reaches_the_prompt_and_is_named_as_grounds() -> None:
    """A grounding judge with no ground cannot tell an accurate paraphrase of a
    retrieved document from an invented one, and a strict judge flags both.

    Observed on KYC Sentinel's kyc_halluc_missing_source_of_funds: the agent
    wrote "[policy-005] (rubric: incomplete source of funds → MEDIUM)", which is
    verbatim what policy-005 says. The judge scored hallucination=0.50 and its
    note read "it hallucinated specific content for policy-005" — because it had
    never been shown policy-005. The agent was right and the harness was blind.
    """
    import eval_judge

    prompt = eval_judge.judge_prompt(
        "inst", "(none)", "Retrieved policies: policy-005", "any",
        "ref", "Basis: [policy-005] (rubric: incomplete source of funds → MEDIUM)",
        include_hallucination=True,
        retrieved_context=[{"id": "policy-005",
                            "text": "MEDIUM: adverse media or incomplete source of funds."}],
    )
    assert "RETRIEVED CONTEXT:" in prompt
    assert "incomplete source of funds" in prompt
    assert "[policy-005]" in prompt
    # The scoring instruction must actually point at it, or supplying the text
    # changes nothing about how the judge weighs a paraphrase.
    assert "INPUT, REFERENCE and RETRIEVED CONTEXT" in prompt
    assert "GROUNDED" in prompt


def test_no_context_means_no_empty_labelled_section() -> None:
    """An empty 'RETRIEVED CONTEXT:' heading reads to a model as "nothing was
    retrieved", which is a different claim from "retrieval is not part of this
    case" — and would invite flagging any document reference as unsupported."""
    import eval_judge

    prompt = eval_judge.judge_prompt(
        "inst", "(none)", "in", "any", "ref", "act", include_hallucination=True,
    )
    assert "RETRIEVED CONTEXT" not in prompt
    assert "INPUT and REFERENCE" in prompt


def test_a_case_carries_its_context_through_judge_case(monkeypatch) -> None:
    """The fixture field has to survive the call path, not just the formatter."""
    import eval_judge

    seen = {}

    # Returns a dict, which is `run_judge`'s actual contract. The previous
    # one-liner was `seen.setdefault("prompt", prompt) or {}` — and setdefault
    # returns the value it just stored, so that expression evaluated to the
    # PROMPT STRING and the `or {}` never fired. It passed only because nothing
    # downstream touched the result; the moment judge_case started stamping
    # `criteria_digest` onto it, the double failed with "'str' object does not
    # support item assignment". A test double that violates the contract of the
    # thing it replaces will pass until the real caller does something ordinary.
    def _fake_run_judge(prompt, model):
        seen["prompt"] = prompt
        return {}

    monkeypatch.setattr(eval_judge, "run_judge", _fake_run_judge)
    eval_judge.judge_case(
        {"id": "c", "input": "in", "score_hallucination": True,
         "actual_output": "out",
         "retrieved_context": [{"id": "policy-002", "text": "Source of funds must be evidenced."}]},
        {}, "some-judge",
    )
    assert "Source of funds must be evidenced." in seen["prompt"]


# ── The suite needs a positive control, and must gate on it ──────────────────


def _h_row(case_id, hallucination, expect=False):
    row = {
        "case_id": case_id, "score": 1.0, "correctness": 1, "tool_accuracy": 1,
        "latency_ms": 0, "quality_notes": "", "judged_by": "j", "error": None,
        "hallucination": hallucination,
    }
    if expect:
        row["expect_hallucination"] = True
    return row


def test_a_planted_case_is_not_counted_as_a_false_positive() -> None:
    """Flagging a planted hallucination is the CORRECT outcome. Counting it in
    the flagged-claim rate would mean a positive control could never be added
    without failing the gate it exists to strengthen — one planted case in six
    scores 0.167 against a 0.05 ceiling."""
    revals = load_script("run-evals")
    rows = [_h_row("clean1", 0.0), _h_row("clean2", 0.0),
            _h_row("ghost", 1.0, expect=True)]
    assert revals.hallucination_flag_rate(rows) == 0.0


def test_a_missed_planted_hallucination_fails_the_suite(monkeypatch, capsys) -> None:
    """The point of the control: if the judge cannot spot a citation to a
    document that was never retrieved, the suite's clean results carry no
    information."""
    revals = load_script("run-evals")
    cases = [{"id": "clean", "input": "x", "score_hallucination": True},
             {"id": "ghost", "input": "x", "score_hallucination": True,
              "expect_hallucination": True},
             {"id": "clean2", "input": "x", "score_hallucination": True}]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _h_row(case["id"], 0.0,
                                     expect=bool(case.get("expect_hallucination"))),
    )

    assert revals.run_scorecard(fail_below=0.5, suite="hallucination") == 1
    out = capsys.readouterr().out
    assert "Detection miss:" in out
    assert "went undetected" in out


def test_a_detected_planted_hallucination_passes(monkeypatch, capsys) -> None:
    revals = load_script("run-evals")
    cases = [{"id": "clean", "input": "x", "score_hallucination": True},
             {"id": "ghost", "input": "x", "score_hallucination": True,
              "expect_hallucination": True},
             {"id": "clean2", "input": "x", "score_hallucination": True}]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(
        revals, "_judge_case",
        lambda case, *a, **k: _h_row(
            case["id"], 1.0 if case.get("expect_hallucination") else 0.0,
            expect=bool(case.get("expect_hallucination"))),
    )

    assert revals.run_scorecard(fail_below=0.5, suite="hallucination") == 0
    out = capsys.readouterr().out
    assert "Detection miss:  0.000" in out
    assert "Hallucination:   0.000" in out, "the planted flag is not a false positive"


def test_a_suite_with_no_positive_control_says_so(monkeypatch, capsys) -> None:
    """"Detected everything" and "was never asked to detect anything" must not
    both render as a clean 0.000 — that is how a suite of only-clean cases reads
    as proof it can catch something."""
    revals = load_script("run-evals")
    cases = [{"id": f"c{i}", "input": "x", "score_hallucination": True} for i in range(3)]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})
    monkeypatch.setattr(revals, "_judge_case",
                        lambda case, *a, **k: _h_row(case["id"], 0.0))

    revals.run_scorecard(fail_below=0.5, suite="hallucination")
    assert "no positive control" in capsys.readouterr().out


def test_an_errored_positive_control_is_not_reported_as_absent(monkeypatch, capsys) -> None:
    """Three states, three messages. Seen live in CI run 32459919051: the
    planted case errored, hallucination_miss_rate returned None because it has
    no verdict to score, and the report printed "no positive control in this
    suite" — while the control sat right there in the fixture.

    That is the same conflation this feature exists to prevent, one level up:
    "nothing to detect" and "could not check" must not read alike.
    """
    revals = load_script("run-evals")
    # Three cases minimum, or the suite skips before it reaches the branch
    # under test — which is itself worth knowing when writing these.
    cases = [{"id": "clean", "input": "x", "score_hallucination": True},
             {"id": "clean2", "input": "x", "score_hallucination": True},
             {"id": "ghost", "input": "x", "score_hallucination": True,
              "expect_hallucination": True}]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})

    def _judge(case, *a, **k):
        planted = bool(case.get("expect_hallucination"))
        row = _h_row(case["id"], 0.0, expect=planted)
        if planted:                       # the control itself could not be graded
            row["error"] = "Provider exhausted"
        return row

    monkeypatch.setattr(revals, "_judge_case", _judge)
    revals.run_scorecard(fail_below=0.5, suite="hallucination")
    out = capsys.readouterr().out
    assert "NOT GRADED" in out
    assert "positive control(s) errored" in out
    assert "no positive control in this suite" not in out, (
        "an ungraded control must not read as an absent one"
    )


def test_a_flag_rate_over_nothing_is_not_reported_as_clean(monkeypatch, capsys) -> None:
    """Zero flagged out of zero measured is not a clean result. Reachable when
    every clean case errors and only planted ones grade — the false-positive
    rate then has nothing to average over, and 0.000 would say the suite looked
    and found nothing wrong."""
    revals = load_script("run-evals")
    cases = [{"id": "c1", "input": "x", "score_hallucination": True},
             {"id": "c2", "input": "x", "score_hallucination": True},
             {"id": "ghost", "input": "x", "score_hallucination": True,
              "expect_hallucination": True}]
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {})

    def _judge(case, *a, **k):
        planted = bool(case.get("expect_hallucination"))
        row = _h_row(case["id"], 1.0 if planted else 0.0, expect=planted)
        if not planted:                      # every CLEAN case fails to grade
            row["error"] = "Provider exhausted"
            row.pop("hallucination", None)
        return row

    monkeypatch.setattr(revals, "_judge_case", _judge)
    revals.run_scorecard(fail_below=0.5, suite="hallucination")
    out = capsys.readouterr().out
    assert "NOT MEASURED" in out
    assert "Hallucination:   0.000" not in out, "no data must not print as a clean rate"


def test_the_flag_rate_helper_returns_none_rather_than_zero() -> None:
    revals = load_script("run-evals")
    assert revals.hallucination_flag_rate([]) is None
    assert revals.hallucination_flag_rate([_h_row("g", 1.0, expect=True)]) is None
    assert revals.hallucination_flag_rate([_h_row("c", 0.0)]) == 0.0


def test_an_errored_control_still_carries_its_expectation(monkeypatch) -> None:
    """The flag is a property of the CASE. It was previously copied onto the row
    only inside `if "hallucination" in scored`, which an errored judge call never
    satisfies — so the control vanished from the count exactly when it mattered,
    and the report claimed the suite had no control at all.

    Guards the row-building contract directly, because the report-level test can
    be satisfied by a row that happens to grade.
    """
    revals = load_script("run-evals")
    monkeypatch.setattr(revals, "_judge_case_scored", None, raising=False)
    import eval_judge
    monkeypatch.setattr(eval_judge, "judge_case",
                        lambda *a, **k: {"error": "Provider exhausted", "score": 0.0,
                                         "correctness": 0, "tool_accuracy": 0})
    row = revals._judge_case(
        {"id": "ghost", "input": "x", "expect_hallucination": True,
         "actual_output": "out", "score_hallucination": True},
        {"score_hallucination": True}, "some-judge", project_response="out",
    )
    assert row.get("error"), "precondition: this row must represent a failed judge call"
    assert row.get("expect_hallucination") is True, (
        "an errored positive control must still be identifiable as a control"
    )


def test_judge_case_row_contract_identity_survives_a_failed_verdict(monkeypatch) -> None:
    """_judge_case builds every result row for every judged suite, and until
    2026-08-21 no test called it — nine tests stubbed it out and asserted the
    REPORTING logic against hand-built rows instead. The stub helper set
    `expect_hallucination` unconditionally while production set it only inside
    `if "hallucination" in scored`, so the fixture encoded the intended contract
    and the code violated it. Those tests could not have failed.

    The rule this pins down: a row carries two kinds of field, and they behave
    oppositely when the judge fails.

      IDENTITY  who the case is and what was expected of it. Comes from the
                case dict, must survive regardless of outcome — the suite still
                needs to know a control was a control when it could not grade.
      VERDICT   what the judge said. Absent or zero when there is no verdict,
                which is what `error` is for.

    Group an identity field with the verdict fields and it disappears exactly
    when something went wrong, which is when it matters most.
    """
    revals = load_script("run-evals")
    import eval_judge
    monkeypatch.setattr(eval_judge, "judge_case",
                        lambda *a, **k: {"error": "boom", "score": 0.0,
                                         "correctness": 0, "tool_accuracy": 0})
    case = {"id": "c1", "input": "some input text", "expected_tool": "search",
            "pair_id": "p1", "protected_attribute": "nationality",
            "attribute_value": "SD", "expect_hallucination": True,
            "actual_output": "out", "score_hallucination": True}
    row = revals._judge_case(case, {"score_fairness": True, "score_hallucination": True},
                             "j", project_response="out")

    assert row.get("error"), "precondition: the judge call must have failed"
    for field in ("case_id", "expected_tool", "pair_id", "protected_attribute",
                  "attribute_value", "expect_hallucination"):
        assert field in row, f"identity field {field!r} lost when the verdict failed"
    # And the converse: a verdict field must NOT be invented out of nothing.
    assert "hallucination" not in row, "no verdict means no hallucination score"
    assert "fairness" not in row, "no verdict means no fairness score"


def test_judge_case_row_contract_full_row(monkeypatch) -> None:
    """Every field _judge_case is responsible for, pinned in one place.

    Split by where the value comes from, because that is what decides its
    behaviour when something fails:

      from the CASE     case_id, input, expected_tool, pair_id and friends
      from the JUDGE    correctness, tool_accuracy, score, quality_notes,
                        judged_by, judged_by_route, error
      measured HERE     latency_ms
    """
    revals = load_script("run-evals")
    import eval_judge
    verdict = {"correctness": 1, "tool_accuracy": 1, "score": 0.75,
               "quality_notes": "adequate", "judged_by": "judge-x",
               "judged_by_route": "groq/judge-x", "error": None,
               "fairness": 1, "hallucination": 0.25}
    monkeypatch.setattr(eval_judge, "judge_case", lambda *a, **k: verdict)

    long_input = "x" * 500
    row = revals._judge_case(
        {"id": "c9", "input": long_input, "expected_tool": "search",
         "actual_output": "out", "pair_id": "p", "score_hallucination": True},
        {"score_fairness": True, "score_hallucination": True}, "judge-x",
        project_response="out",
    )

    assert row["case_id"] == "c9"
    assert row["expected_tool"] == "search"
    # Truncated deliberately: a results artifact that embeds full prompts grows
    # without bound and leaks case content into a file people paste around.
    assert len(row["input"]) == 120, "input must stay truncated in the stored row"
    assert row["correctness"] == 1 and row["tool_accuracy"] == 1
    assert row["score"] == 0.75 and isinstance(row["score"], float)
    assert row["quality_notes"] == "adequate"
    assert row["fairness"] == 1
    assert row["hallucination"] == 0.25
    # Per-case provenance, not a run-level field: a judge substituted mid-run is
    # only visible if each verdict records who produced it and where it was served.
    assert row["judged_by"] == "judge-x"
    assert row["judged_by_route"] == "groq/judge-x"
    assert row["error"] is None
    assert isinstance(row["latency_ms"], int)


def test_a_missing_verdict_field_defaults_rather_than_raising(monkeypatch) -> None:
    """A judge that answers with a partial object must not crash the run — the
    suite's job is to report a bad verdict, not to die on one."""
    revals = load_script("run-evals")
    import eval_judge
    monkeypatch.setattr(eval_judge, "judge_case", lambda *a, **k: {})
    row = revals._judge_case(
        {"id": "c", "input": "x", "actual_output": "o"}, {}, "j", project_response="o")
    assert row["correctness"] == 0 and row["tool_accuracy"] == 0
    assert row["score"] == 0.0
    assert row["quality_notes"] == ""
    assert row["judged_by"] is None


def test_a_starved_run_annotates_the_github_run_page(tmp_path, monkeypatch, capsys) -> None:
    """Exit 0 plus a green check is how a gate stops grading unnoticed.

    The no-verdict path must stay exit 0 — an unreachable judge is an
    infrastructure state — but it must not also be invisible.
    """
    revals = load_script("run-evals")
    # ≥3 cases, or the suite skips before it ever reaches the judge.
    cases = [
        {"id": f"h{n}", "input": "a", "actual_output": "a"} for n in range(1, 4)
    ]

    def erroring_judge(case: dict, criteria: dict, judge: str) -> dict:
        return {
            "case_id": case["id"], "input": case["input"], "expected_tool": "any",
            "latency_ms": 0, "correctness": 0, "tool_accuracy": 0, "score": 0.0,
            "quality_notes": "", "error": "429 RESOURCE_EXHAUSTED",
        }

    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(revals, "_load_criteria", lambda suite: {"name": "Hallucination"})
    monkeypatch.setattr(revals, "_judge_case", erroring_judge)
    monkeypatch.setattr(revals, "_results_path", lambda suite: tmp_path / "r.json")

    assert revals.run_scorecard(fail_below=0.8, suite="hallucination") == 0

    out = capsys.readouterr().out
    assert "::warning title=" in out
    assert "proves nothing" in out
    # Single-line: everything after a raw newline is dropped by the runner.
    annotation = next(ln for ln in out.splitlines() if ln.startswith("::warning"))
    assert "%0A" in annotation
    assert "no hallucination evidence" in summary.read_text()


def test_no_annotation_outside_github_actions(tmp_path, monkeypatch, capsys) -> None:
    revals = load_script("run-evals")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    revals._github_warning("t", "m")
    assert "::warning" not in capsys.readouterr().out

# Two tests that lived here now live in the tenant's own repo, as
# `test/test_hallucination_fixture.py`: one asserting every `retrieved_context`
# id exists in that tenant's corpus, one asserting its suite has a positive
# control. Both were assertions about a TENANT's data, reached through
# `../KYC_Sentinel`, and both returned silently when the sibling was absent —
# which is every CI runner, since the framework's CI does not check a tenant
# out. They had never run where it counted.


def test_a_failing_gate_prints_the_reason_it_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The ❌ must be accompanied by the sub-verdict that caused it.

    Each sub-verdict — parity, hallucination rate, the guard ceiling, a missed
    positive control — was computed at the gate and RE-DERIVED three hundred
    lines later for its reason line. One of the four had already drifted: the
    "Failing pairs" list used `fail_below` while the gate that failed them used
    `parity_floor`. Fixing that one in isolation left its three neighbours in
    the shape that produced it.

    They are named once and reused now. Nothing asserted the reason lines print
    at all, which is why the drift could happen quietly — a suite of tests on
    the verdict and none on the explanation.
    """
    revals = load_script("run-evals")
    cases = [
        {"id": "h1", "input": "a", "actual_output": "a"},
        {"id": "h2", "input": "b", "actual_output": "b"},
        {"id": "h3", "input": "c", "actual_output": "c"},
    ]
    verdicts = iter([0.0, 0.6, 1.0])

    def fake_judge_case(case: dict, criteria: dict, judge: str) -> dict:
        return {
            "case_id": case["id"], "input": case["input"], "expected_tool": "any",
            "latency_ms": 0, "correctness": 1, "tool_accuracy": 1, "score": 1.0,
            "quality_notes": "", "error": None, "hallucination": next(verdicts),
        }

    monkeypatch.setattr(revals, "_load_cases", lambda suite: cases)
    monkeypatch.setattr(
        revals, "_load_criteria",
        lambda suite: {"name": "Hallucination", "score_hallucination": True},
    )
    monkeypatch.setattr(revals, "_judge_case", fake_judge_case)
    monkeypatch.setattr(revals, "_results_path", lambda suite: tmp_path / "r.json")

    assert revals.run_scorecard(
        fail_below=0.8, suite="hallucination", hallucination_fail_above=0.5
    ) == 1

    out = capsys.readouterr().out
    assert "Hallucination gate failed" in out, (
        "the suite failed on the hallucination rate and never said so"
    )
    assert "0.667 > 0.500" in out, "the reason line does not show the two numbers"
