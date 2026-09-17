"""
scripts/test/test_gate_pillars.py — G6a: pillar answers that can be checked,
and the two pillars a script can check by itself.

Sixteen lines of "P<n> applies — it does" is a form, not a control. An answer
now names something resolvable — a path, a test id, a span name, in backticks —
and the gate resolves it against what the commit tracks. It proves the token
resolves, not that it is the right one; a name someone else can look up is
falsifiable, and prose is not.

The mechanical half is the other direction: P3 and P7 are checked in the code
itself, over the files a commit touches. A repo that adopts the policy does not
have to fix everything it already owns — that is what the allowlist is for —
but the allowlist only ratchets: entries need the owner's approval to appear,
and the mode may not be weakened, so it cannot be widened by switching the
policy off and on again.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import (
    DESIGN,
    TOKEN,
    DESIGN_PILLARS,
    MESSAGE,
    REPO,
    REVIEW_CLEAN,
    _commit,
    _git,
    _write,
    needs_git,
)

pytestmark = needs_git

sys.path.insert(0, str(REPO / "scripts"))
import gate_models as gm
import gate_pillars as gp

CONFIG = ".agenticframework/process-gates.json"
ANSWER = f"- {DESIGN_PILLARS} applies — each was worked for {TOKEN}."
# The shared DESIGN already names something: what a design looked like before
# the rule is the interesting case here.
PROSE = DESIGN.replace(ANSWER, f"- {DESIGN_PILLARS} applies — each was worked for this change.")
# The policy lives in a gated file, so a commit that changes it needs a design
# whose scope says so.
POLICY_DESIGN = DESIGN.replace("  - scripts/tool.py\n", "  - scripts/tool.py\n  - " + CONFIG + "\n")
TESTS_DESIGN = DESIGN.replace("  - scripts/tool.py\n", "  - scripts/tool.py\n  - scripts/test/**\n")


def _policy(repo: Path, value, commit: bool = True) -> None:
    """Set (or remove) this repo's pillar policy. Committed with the gate off by
    default: the ratchet judges the commits that come after it."""
    path = repo / CONFIG
    config = json.loads(path.read_text(encoding="utf-8"))
    if value is None:
        config.pop("pillars", None)
    else:
        config["pillars"] = value
    path.write_text(json.dumps(config, indent=2) + "\n")
    if commit:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "chore: pillar policy", "--no-verify")


def _records(repo: Path, design: str = DESIGN) -> None:
    _write(repo, ".agent-rfc/designs/change.md", design)
    _write(repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)


@pytest.fixture()
def enforcing(gated_repo):
    _policy(gated_repo, "enforce")
    return gated_repo


# ── evidence tokens ──────────────────────────────────────────────────────────


def test_an_applies_answer_without_a_token_is_refused(enforcing):
    _records(enforcing, PROSE)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "names nothing" in result.stderr, result.stderr


def test_an_applies_answer_that_names_a_tracked_path_passes(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode == 0, result.stderr


def test_a_token_that_resolves_to_nothing_is_refused(enforcing):
    _records(enforcing, DESIGN.replace(TOKEN, "`scripts/deleted.py`"))
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "scripts/deleted.py" in result.stderr


def test_a_test_id_resolves_by_the_content_that_holds_it(enforcing):
    """One rule covers a path, a test id and a span name: the token is either a
    tracked path or text a tracked source file holds."""
    _write(enforcing, "scripts/test/test_tool.py", "def test_the_tool_retries():\n    assert True\n")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "test: the retry test", "--no-verify")
    _records(enforcing, DESIGN.replace(TOKEN, "`test_the_tool_retries`"))
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode == 0, result.stderr


def test_a_token_the_record_itself_invents_does_not_vouch_for_it(enforcing):
    """Records are markdown, and a design that could resolve its own token
    would make the check self-certifying."""
    _records(enforcing, DESIGN.replace(TOKEN, "`the-retry-ladder`"))
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "the-retry-ladder" in result.stderr


def test_n_a_and_gap_answers_need_no_token(enforcing):
    answers = "\n".join([
        "- P1, P2, P3, P4, P7, P11, P12, P13, P14, P16 applies — `scripts/process_gate.py`.",
        "- P8, P9, P10 n/a — this change calls no model and wires no exporter.",
        "- P15 gap — PB-402 covers the message audit.",
    ])
    _records(enforcing, DESIGN.replace(ANSWER, answers))
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode == 0, result.stderr


def test_off_asks_for_no_evidence(gated_repo):
    _policy(gated_repo, None)
    _records(gated_repo, PROSE)
    _write(gated_repo, "scripts/tool.py", "print(1)\n")

    assert _commit(gated_repo, MESSAGE).returncode == 0


# ── mechanical checks ────────────────────────────────────────────────────────

DATACLASS = "from dataclasses import dataclass\n\n\n@dataclass\nclass Rung:\n    delay: int\n"
ROUTE = (
    'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/healthz")\n'
    "async def healthz():\n    return {}\n"
)
TRACED_ROUTE = (
    'from fastapi import FastAPI\nfrom runtime.tracing import agent_span\n\napp = FastAPI()\n\n\n'
    '@app.get("/healthz")\nasync def healthz():\n    with agent_span("healthz"):\n        return {}\n'
)


def test_a_dataclass_in_a_touched_file_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-pydantic" in result.stderr and "scripts/tool.py" in result.stderr


def test_importing_dataclasses_is_flagged_without_a_decorated_class(enforcing):
    """`dataclasses.make_dataclass`, or an import kept for later: the module
    still builds its models the wrong way."""
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", "import dataclasses\n\nRung = dataclasses.make_dataclass('Rung', ['delay'])\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-pydantic" in result.stderr


def test_a_route_that_opens_no_span_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", ROUTE)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P3-tracing" in result.stderr and "healthz" in result.stderr


def test_a_route_inside_a_span_passes(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", TRACED_ROUTE)

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_a_test_file_is_not_first_party_code(enforcing):
    """A fixture is not a model; flagging test files would teach everyone to
    allowlist the directory. The file has to be IN the commit under test —
    the checks read what a commit touches."""
    _records(enforcing, TESTS_DESIGN)
    _write(enforcing, "scripts/test/test_rung.py", DATACLASS)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode == 0, result.stderr


def test_an_allowlisted_path_is_not_refused(enforcing):
    _policy(enforcing, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "scripts/tool.py", "why": "value object, pre-existing at adoption"},
    ]})
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_an_allowlist_entry_covers_one_check_only(enforcing):
    _policy(enforcing, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "scripts/tool.py", "why": "value object"},
    ]})
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", ROUTE)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P3-tracing" in result.stderr


def test_report_says_what_would_fail_without_failing(enforcing):
    _policy(enforcing, "report")
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode == 0, result.stderr
    # git gives a hook's own output to the terminal, which is stderr here.
    assert "P7-pydantic" in result.stdout + result.stderr


def test_report_does_not_block_on_a_pillar_answer_either(enforcing):
    """`report` has to mean the same thing for both halves of the policy."""
    _policy(enforcing, "report")
    _records(enforcing, PROSE)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode == 0, result.stderr
    assert "names nothing" in result.stdout + result.stderr


def test_a_check_whose_pillar_is_not_mechanical_does_not_run(enforcing):
    """Which checks exist is the registry's to say — a repo that syncs a
    registry without the mechanical mark is not held to it."""
    registry = json.loads((enforcing / "templates" / "governance.json").read_text(encoding="utf-8"))
    for pillar in registry["pillars"]:
        pillar["check"] = [k for k in pillar["check"] if k != "mechanical"] or ["design"]
    _write(enforcing, "templates/governance.json", json.dumps(registry, indent=2) + "\n")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a registry without mechanical checks", "--no-verify")
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    assert _commit(enforcing, MESSAGE).returncode == 0


# ── the ratchet ──────────────────────────────────────────────────────────────


def test_a_new_allowlist_entry_needs_the_owners_approval(enforcing):
    _policy(enforcing, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "scripts/tool.py", "why": "I would rather not"},
    ]}, commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "agentsmith approve" in result.stderr


def test_an_approved_entry_is_accepted(enforcing):
    approval = {
        "id": "A-0123abcd", "design": ".agent-rfc/designs/change.md", "deviation": "D1",
        "approver": "owner", "approved_at": "2026-09-17T00:00:00Z", "channel": "tty",
        "statement": "allowlist scripts/tool.py for P7-pydantic",
    }
    _write(enforcing, ".agenticframework/approvals.jsonl", json.dumps(approval) + "\n")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: the owner's approval", "--no-verify")
    _policy(enforcing, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "scripts/tool.py", "why": "value object", "approval": "A-0123abcd"},
    ]}, commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_an_approved_entry_is_accepted_only_when_the_owner_recorded_it(enforcing):
    """An id nobody recorded is a string the agent typed."""
    _policy(enforcing, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "scripts/tool.py", "why": "value object", "approval": "A-deadbeef"},
    ]}, commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "A-deadbeef" in result.stderr and "approvals.jsonl" in result.stderr


def test_removing_an_entry_needs_nothing(enforcing):
    _policy(enforcing, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "scripts/tool.py", "why": "value object"},
    ]})
    _policy(enforcing, "enforce", commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_the_mode_may_not_be_weakened(enforcing):
    _policy(enforcing, "report", commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "weaken" in result.stderr.lower()


def test_dropping_the_policy_is_a_weakening(enforcing):
    """Or the allowlist could be widened by turning the policy off and on."""
    _policy(enforcing, None, commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "weaken" in result.stderr.lower()


def test_the_first_policy_a_repo_declares_is_its_seed(gated_repo):
    _policy(gated_repo, None)
    _policy(gated_repo, {"mode": "enforce", "allow": [
        {"check": "P7-pydantic", "path": "runtime/llm_gateway.py", "why": "pre-existing at adoption"},
    ]}, commit=False)
    _records(gated_repo, POLICY_DESIGN)
    _write(gated_repo, "scripts/tool.py", "print(1)\n")

    assert _commit(gated_repo, MESSAGE).returncode == 0


def test_an_entry_says_why_it_is_there(enforcing):
    _policy(enforcing, {"mode": "enforce", "allow": [{"check": "P7-pydantic", "path": "scripts/tool.py"}]},
            commit=False)
    _records(enforcing, POLICY_DESIGN)
    _write(enforcing, "scripts/tool.py", "print(1)\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "why" in result.stderr


# ── the command, and one verdict ─────────────────────────────────────────────


def _pillars(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "process_gate.py"), "pillars", *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def test_the_command_lists_what_the_repo_owns_today(enforcing):
    _write(enforcing, "scripts/tool.py", DATACLASS)
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a dataclass", "--no-verify")

    result = _pillars(enforcing)

    assert result.returncode != 0
    assert "scripts/tool.py" in result.stdout and "P7-pydantic" in result.stdout


def test_the_command_says_off_when_the_repo_has_no_policy(gated_repo):
    _policy(gated_repo, None)
    result = _pillars(gated_repo)

    assert result.returncode == 0
    assert "off" in result.stdout.lower()


def test_the_command_does_not_call_an_unchecked_repo_clean(enforcing):
    """"Nothing was checked" and "everything passed" are different answers."""
    registry = json.loads((enforcing / "templates" / "governance.json").read_text(encoding="utf-8"))
    for pillar in registry["pillars"]:
        pillar["check"] = [k for k in pillar["check"] if k != "mechanical"] or ["design"]
    _write(enforcing, "templates/governance.json", json.dumps(registry, indent=2) + "\n")

    result = _pillars(enforcing)

    assert result.returncode == 0
    assert "marks no pillar" in result.stdout and "not the same as passing" in result.stdout


def test_an_unknown_mode_is_refused_rather_than_ignored(enforcing):
    _policy(enforcing, "enforced", commit=False)

    result = _pillars(enforcing)

    assert result.returncode == 1
    assert "pillars" in result.stdout and "enforced" in result.stdout


def test_report_mode_reports_in_the_command_too(enforcing):
    _policy(enforcing, "report")
    _write(enforcing, "scripts/tool.py", DATACLASS)
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a dataclass", "--no-verify")

    result = _pillars(enforcing)

    assert result.returncode == 0, result.stdout
    assert "scripts/tool.py" in result.stdout


# ── the framework's own registry and config ──────────────────────────────────


def test_every_implemented_check_belongs_to_a_mechanical_pillar() -> None:
    registry = gm.Registry.model_validate_json(
        (REPO / "templates" / "governance.json").read_text(encoding="utf-8"))
    mechanical = {p.id for p in registry.pillars if "mechanical" in p.check}
    assert mechanical, "the shipped registry marks no pillar mechanical"
    for check_id, check in gp.CHECKS.items():
        assert check.pillar in mechanical, f"{check_id} has no mechanical pillar in the registry"


def test_the_framework_holds_itself_to_the_policy_it_ships() -> None:
    config = json.loads((REPO / CONFIG).read_text(encoding="utf-8"))
    policy, problems = gp.parse_policy(config.get("pillars"))
    assert problems == []
    assert policy.mode == "enforce", "AgentSmith runs the check it ships"
    assert all(entry.why for entry in policy.allow)
