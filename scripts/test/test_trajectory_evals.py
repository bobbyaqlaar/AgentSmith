"""The trajectory suite: graded from the calls, not by a model (.agent-rfc/designs/trajectory-evals.md)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import evals_port
import gate_models as gm


def _expect(**rules) -> gm.TrajectoryExpect:
    return gm.TrajectoryExpect(**rules)


@pytest.mark.parametrize("tools, rules, broken", [
    (["lookup", "score", "decide"], {"in_order": ["lookup", "decide"]}, []),
    (["decide", "lookup"], {"in_order": ["lookup", "decide"]}, ["did not call decide"]),
    (["lookup", "lookup"], {"in_order": ["lookup", "lookup"]}, []),
    (["lookup"], {"in_order": ["lookup", "lookup"]}, ["did not call lookup"]),
    (["lookup", "delete_user"], {"never": ["delete_user"]}, ["called delete_user"]),
    (["score"], {"must_call": ["lookup"]}, ["never called lookup"]),
    (["a", "b", "c"], {"max_calls": 2}, ["made 3 tool calls, more than 2"]),
    (["a", "b"], {"max_calls": 2}, []),
    ([], {"max_calls": 0}, []),
])
def test_each_rule(tools, rules, broken):
    problems = evals_port.trajectory_problems(tools, _expect(**rules))
    assert len(problems) == len(broken)
    for got, want in zip(problems, broken, strict=True):
        assert got.startswith(want)


def test_a_case_needs_a_rule_and_exactly_one_source():
    with pytest.raises(gm.ValidationError):
        gm.TrajectoryExpect()
    with pytest.raises(gm.ValidationError):
        gm.TrajectoryCase(id="a", expect={"never": ["x"]})
    with pytest.raises(gm.ValidationError):
        gm.TrajectoryCase(id="a", tools=[], trace="t.json", expect={"never": ["x"]})


def _span(name: str, start: int, key: str = "gen_ai.tool.name") -> dict:
    return {"name": f"agent.tool.{name}", "startTimeUnixNano": str(start),
            "attributes": [{"key": key, "value": {"stringValue": name}}]}


def _otlp(*spans: dict) -> dict:
    return {"resourceSpans": [{"scopeSpans": [{"spans": list(spans)}]}]}


def _run(tmp_path: Path, cases: list[dict], files: dict[str, str] | None = None, **request) -> gm.Scorecard:
    fixtures = tmp_path / ".agent-rfc" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "trajectory_evals.json").write_text(json.dumps(cases), encoding="utf-8")
    for rel, text in (files or {}).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return evals_port.judge_trajectory(tmp_path, gm.EvalsRequest(suite="trajectory", **request))


KEPT = {"id": "kept", "tools": ["lookup", "decide"], "expect": {"in_order": ["lookup", "decide"]}}
BROKEN = {"id": "broken", "tools": ["decide"], "expect": {"must_call": ["lookup"]}}


def test_every_run_keeping_its_rules_passes(tmp_path):
    card = _run(tmp_path, [KEPT])
    assert (card.verdict, card.cases_graded) == ("pass", 1)


def test_one_broken_run_fails_at_the_default_floor_and_is_named(tmp_path):
    card = _run(tmp_path, [KEPT, BROKEN])
    assert card.verdict == "fail" and "broken: never called lookup" in card.reason


def test_a_declared_floor_lowers_the_bar(tmp_path):
    assert _run(tmp_path, [KEPT, BROKEN], fail_below=0.5).verdict == "pass"


def test_no_dataset_is_not_gradable(tmp_path):
    card = evals_port.judge_trajectory(tmp_path, gm.EvalsRequest(suite="trajectory"))
    assert card.verdict == "not_gradable"


def test_calls_are_read_from_a_trace_in_start_order(tmp_path):
    trace = _otlp(_span("decide", 20), _span("lookup", 10, key="agent.tool.name"),
                  {"name": "llm.call", "startTimeUnixNano": "5", "attributes": []})
    case = {"id": "t", "trace": "traces/run.json", "expect": {"in_order": ["lookup", "decide"], "max_calls": 2}}
    assert _run(tmp_path, [case], {"traces/run.json": json.dumps(trace)}).verdict == "pass"


def test_a_trace_written_one_object_per_line_is_read(tmp_path):
    lines = "\n".join(json.dumps(_otlp(_span(n, i))) for i, n in enumerate(["lookup", "decide"]))
    case = {"id": "t", "trace": "run.jsonl", "expect": {"in_order": ["lookup", "decide"]}}
    assert _run(tmp_path, [case], {"run.jsonl": lines}).verdict == "pass"


@pytest.mark.parametrize("trace, text, why", [
    ("../outside.json", None, "outside the repository"),
    ("missing.json", None, "cannot be read"),
    ("bad.json", "not json at all", "not OTLP/JSON"),
    ("empty.json", json.dumps({"resourceSpans": []}), "holds no spans"),
])
def test_a_trace_that_cannot_be_read_is_not_gradable(tmp_path, trace, text, why):
    files = {trace: text} if text is not None else {}
    card = _run(tmp_path, [{"id": "t", "trace": trace, "expect": {"never": ["x"]}}], files)
    assert card.verdict == "not_gradable" and why in card.reason


def test_the_cli_and_the_hook_accept_the_suite():
    hook = (REPO / ".githooks" / "process-gate").read_text(encoding="utf-8")
    assert "|rag_poison|trajectory) ;;" in hook
    cli = (REPO / "agentsmith" / "cli.py").read_text(encoding="utf-8")
    assert '"rag_poison", "trajectory"' in cli
