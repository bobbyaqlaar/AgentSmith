"""
runtime/test/test_conformance.py — the gate contract's conformance runner
(.agent-rfc/designs/gate-port.md).

The runner builds the fixture repository the contract describes, replays each
case against a provider command, and reports per case. These tests drive it with
stub providers — a correct one, a wrong one, one that cannot run — because the
runner's own verdicts are what a provider author reads.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from runtime import conformance

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


def _stub(tmp_path: Path, body: str, name: str = "provider") -> str:
    """A provider command: python, so it runs the same on any machine."""
    script = tmp_path / f"{name}.py"
    script.write_text("import json, sys\n" + body)
    return f"{sys.executable} {script}"


ALWAYS_ALLOW = """
event = json.load(sys.stdin)
print(json.dumps({"decision": "allow", "text": ""}))
"""

CANNOT_RUN = """
sys.stderr.write("no framework here\\n")
sys.exit(3)
"""


def test_the_contract_ships_its_cases_and_fixture():
    cases = conformance.cases()
    assert len(cases) >= 5
    assert {c.event_name for c in cases} == {"session-start", "pre-edit", "stop"}
    assert {c.expect for c in cases} <= {"allow", "deny", "block", "context"}
    assert conformance.fixture()["files"], "the fixture repository describes files to write"


@needs_git
def test_a_provider_that_always_allows_fails_the_cases_that_must_refuse(tmp_path):
    report = conformance.run(_stub(tmp_path, ALWAYS_ALLOW), tmp_path / "work")

    assert not report.passed
    failed = [r for r in report.results if not r.ok]
    assert {r.case.expect for r in failed} >= {"deny", "block"}
    assert all(r.actual == "allow" for r in failed)
    assert "expected deny" in report.render() and "got allow" in report.render()


@needs_git
def test_a_provider_that_cannot_run_is_reported_as_that_not_as_a_wrong_answer(tmp_path):
    report = conformance.run(_stub(tmp_path, CANNOT_RUN), tmp_path / "work")

    assert not report.passed
    assert all(r.unavailable for r in report.results)
    assert "cannot run" in report.render()
    assert "expected" not in report.render(), "a provider that never answered has no wrong answers"


@needs_git
def test_a_refusal_with_no_reason_is_not_an_answer(tmp_path):
    """`deny` and `block` carry text a person reads; the wording is free."""
    silent = _stub(tmp_path, """
event = json.load(sys.stdin)
print(json.dumps({"decision": "deny", "text": ""}))
""")

    report = conformance.run(silent, tmp_path / "work")

    reasons = [r for r in report.results if r.case.expect == "deny" and not r.ok]
    assert reasons and any("no reason" in r.why for r in reasons)


@needs_git
def test_a_provider_whose_output_is_not_a_decision_fails_with_what_it_printed(tmp_path):
    noise = _stub(tmp_path, """
sys.stdin.read()
print("I am not JSON")
""")

    report = conformance.run(noise, tmp_path / "work")

    assert not report.passed
    assert "not a decision" in report.render() and "I am not JSON" in report.render()
