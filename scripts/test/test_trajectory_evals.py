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


# ── Tokens per run (.agent-rfc/designs/run-token-limits.md) ──────────────────
def _model_span(start: int, tokens_in: int, tokens_out: int, names: str = "gen_ai") -> dict:
    keys = (("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens") if names == "gen_ai"
            else ("llm.usage.input_tokens", "llm.usage.output_tokens"))
    return {"name": "llm.call", "startTimeUnixNano": str(start), "attributes": [
        {"key": keys[0], "value": {"intValue": str(tokens_in)}},
        {"key": keys[1], "value": {"intValue": str(tokens_out)}}]}


def test_a_run_over_its_token_budget_fails_read_from_its_model_spans(tmp_path):
    trace = _otlp(_model_span(1, 300, 100), _span("lookup", 2), _model_span(3, 500, 200, names="llm"))
    case = {"id": "t", "trace": "run.json", "expect": {"max_tokens": 1000}}
    card = _run(tmp_path, [case], {"run.json": json.dumps(trace)})
    assert card.verdict == "fail" and "spent 1100 tokens, more than 1000" in card.reason


def test_a_span_with_both_name_sets_is_counted_once(tmp_path):
    span = _model_span(1, 300, 100)
    span["attributes"] += _model_span(1, 300, 100, names="llm")["attributes"]
    case = {"id": "t", "trace": "run.json", "expect": {"max_tokens": 400}}
    assert _run(tmp_path, [case], {"run.json": json.dumps(_otlp(span))}).verdict == "pass"


def test_recorded_tokens_count_for_a_named_trajectory(tmp_path):
    case = {"id": "t", "tools": ["lookup"], "tokens": 900, "expect": {"max_tokens": 800}}
    assert _run(tmp_path, [case]).verdict == "fail"


def test_a_token_budget_with_no_tokens_recorded_is_not_gradable(tmp_path):
    card = _run(tmp_path, [{"id": "t", "tools": ["lookup"], "expect": {"max_tokens": 800}}])
    assert card.verdict == "not_gradable" and "records no tokens" in card.reason


# ── The 4.1.0 release review: R2, R11 ──


def _unmeasured_model_span(start: int, *, reported_flag: bool = True) -> dict:
    attributes = [{"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                  {"key": "gen_ai.request.model", "value": {"stringValue": "m"}}]
    if reported_flag:
        attributes.append({"key": "llm.usage.reported", "value": {"boolValue": False}})
    return {"name": "llm.call", "startTimeUnixNano": str(start), "attributes": attributes}


@pytest.mark.parametrize("spans", [
    pytest.param(lambda: [_span("lookup", 1), _unmeasured_model_span(2)], id="usage-not-reported"),
    pytest.param(lambda: [_span("lookup", 1), _unmeasured_model_span(2, reported_flag=False)], id="no-usage-names"),
    pytest.param(lambda: [_model_span(1, 3, 2), _unmeasured_model_span(2)], id="one-of-two-unmeasured"),
    pytest.param(lambda: [_span("lookup", 1)], id="no-model-span"),
])
def test_a_token_budget_nobody_measured_is_not_gradable(tmp_path, spans):
    """R2: a model span with no usage read as 0 tokens, and the case passed."""
    case = {"id": "t", "trace": "run.json", "expect": {"max_tokens": 10}}
    card = _run(tmp_path, [case], {"run.json": json.dumps(_otlp(*spans()))})
    assert card.verdict == "not_gradable" and "records no tokens" in card.reason


def test_an_empty_case_file_is_not_gradable(tmp_path):
    """R11: `[]` raised ZeroDivisionError instead of a scorecard."""
    card = _run(tmp_path, [])
    assert card.verdict == "not_gradable" and "no cases" in card.reason


# ── The 4.1.0 review's second pass: P2-R3 (.agent-rfc/designs/caps-at-load-and-guard-tests.md) ──


def _span_with(*attributes: tuple[str, dict]) -> dict:
    return {"name": "llm.call", "startTimeUnixNano": "2",
            "attributes": [{"key": "gen_ai.request.model", "value": {"stringValue": "m"}},
                           *({"key": key, "value": value} for key, value in attributes)]}


@pytest.mark.parametrize("span", [
    pytest.param(_span_with(("gen_ai.usage.input_tokens", {"boolValue": True}),
                            ("gen_ai.usage.output_tokens", {"boolValue": True})), id="booleans-are-not-counts"),
    pytest.param(_span_with(("gen_ai.usage.input_tokens", {"intValue": "0"}),
                            ("gen_ai.usage.output_tokens", {"intValue": "0"}),
                            ("llm.usage.reported", {"boolValue": False})), id="reported-false-beside-zeros"),
])
def test_a_count_that_is_not_a_measurement_is_not_gradable(tmp_path, span):
    """P2-R3: both guards could be removed with every test green."""
    case = {"id": "t", "trace": "run.json", "expect": {"max_tokens": 10}}
    card = _run(tmp_path, [case], {"run.json": json.dumps(_otlp(_span("lookup", 1), span))})
    assert card.verdict == "not_gradable" and "records no tokens" in card.reason
