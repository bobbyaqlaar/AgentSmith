"""
scripts/test/test_gate_pillars.py — G6: pillar answers that can be checked, and
the pillars a script can check by itself.

Sixteen lines of "P<n> applies — it does" is a form, not a control. An answer
now names something resolvable — a path, a test id, a span name, in backticks —
and the gate resolves it against what the commit tracks. It proves the token
resolves, not that it is the right one; a name someone else can look up is
falsifiable, and prose is not.

The mechanical half is the other direction: P2, P3, P7, P10 and P12 are checked
in the code itself, over the files a commit touches. A repo that adopts the policy does not
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


def _design(*scope: str) -> str:
    """The shared design with more paths in its scope — the gate refuses a
    commit whose gated files the design does not cover."""
    return DESIGN.replace("  - scripts/tool.py\n",
                          "  - scripts/tool.py\n" + "".join(f"  - {path}\n" for path in scope))


# The policy lives in a gated file, so a commit that changes it needs a design
# whose scope says so.
POLICY_DESIGN = _design(CONFIG)
TESTS_DESIGN = _design("scripts/test/**")


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

# A model at a boundary: built out of data the code did not write. This is
# what P7-pydantic flags — an internal value object (VALUE_OBJECT below) is not
# a model, which is the G6b narrowing.
DATACLASS = (
    "import json\n"
    "from dataclasses import dataclass\n\n\n"
    "@dataclass\nclass Payload:\n    amount: int\n\n\n"
    "def load(raw):\n    return Payload(**json.loads(raw))\n"
)
ROUTE = (
    'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/healthz")\n'
    "async def healthz():\n    return {}\n"
)
TRACED_ROUTE = (
    'from fastapi import FastAPI\nfrom runtime.tracing import agent_span\n\napp = FastAPI()\n\n\n'
    '@app.get("/healthz")\nasync def healthz():\n    with agent_span("healthz"):\n        return {}\n'
)


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


def test_the_count_is_of_exemptions_taken_not_markers_written(enforcing):
    """A printed number is one someone can watch grow — as long as it counts
    exemptions taken, not the sentences explaining them."""
    _write(enforcing, "docs/how-secrets-work.md", f"A line that must hold one ends `# {gp.NOT_A_SECRET} why`.\n")
    _write(enforcing, "scripts/tool.py", SECRET_LINE.rstrip("\n") + f"  # {gp.NOT_A_SECRET} fixture\n")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "docs: the marker, and one use of it", "--no-verify")

    assert gp.exemption_count(enforcing) == 1


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


# ── G6b: the rest of the checks ──────────────────────────────────────────────
#
# A check that is new cannot be allowlisted into existence — the ratchet cannot
# tell a new rule from a repo giving itself a pass — so each of these is a rule
# a repo has to satisfy or have the owner exempt. They are narrow on purpose.


VALUE_OBJECT = (
    "from dataclasses import dataclass\n\n\n"
    "@dataclass(frozen=True)\nclass Rung:\n    delay: int\n\n\n"
    "def first():\n    return Rung(delay=1)\n"
)


def test_a_dataclass_built_from_data_the_code_did_not_write_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", DATACLASS)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-pydantic" in result.stderr and "Payload" in result.stderr


def test_unpacking_a_validated_model_is_not_a_boundary(enforcing):
    """`X(**row.model_dump())` is built from data this code just validated. The
    rule is "built from data the code did not write", and flagging this teaches
    people to write every field out at the call site to quiet a checker."""
    _records(enforcing)
    _write(enforcing, "scripts/tool.py",
           "from dataclasses import dataclass\nfrom pydantic import BaseModel\n\n\n"
           "@dataclass\nclass Payload:\n    amount: int\n\n\n"
           "class Row(BaseModel):\n    amount: int\n\n\n"
           "def build(row: Row):\n    return Payload(**row.model_dump())\n")

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_an_internal_value_object_is_not_a_model(enforcing):
    """The narrowing: a dataclass built by keyword from values in the same
    module validates nothing, so requiring Pydantic there is ritual."""
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", VALUE_OBJECT)

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_a_dataclass_that_is_a_request_body_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py",
           'from dataclasses import dataclass\nfrom fastapi import FastAPI\nfrom runtime.tracing import agent_span\n\n'
           'app = FastAPI()\n\n\n@dataclass\nclass Order:\n    sku: str\n\n\n'
           '@app.post("/orders")\nasync def create(order: Order):\n'
           '    with agent_span("create"):\n        return order\n')

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-pydantic" in result.stderr


def test_a_route_handler_that_blocks_the_loop_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py",
           'from fastapi import FastAPI\nfrom runtime.tracing import agent_span\n\napp = FastAPI()\n\n\n'
           '@app.get("/healthz")\ndef healthz():\n    with agent_span("healthz"):\n        return {}\n')

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-async" in result.stderr and "healthz" in result.stderr


def test_an_async_handler_passes(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", TRACED_ROUTE)

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_any_in_typescript_is_refused(enforcing):
    _records(enforcing, _design("portal/**"))
    _write(enforcing, "portal/lib/rows.ts", "export function toRow(r: any) {\n  return r;\n}\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-ts-any" in result.stderr


def test_the_word_any_in_a_comment_is_not_a_type(enforcing):
    _records(enforcing, _design("portal/**"))
    _write(enforcing, "portal/lib/rows.ts",
           "// takes any row shape the view sends: any\nexport function toRow(r: unknown) {\n  return r;\n}\n")

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_a_next_component_using_hooks_needs_use_client(enforcing):
    _records(enforcing, _design("portal/**"))
    _write(enforcing, "portal/next.config.mjs", "export default {};\n")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a next app", "--no-verify")
    _write(enforcing, "portal/components/Counter.tsx",
           "import { useState } from 'react';\n\nexport function Counter() {\n"
           "  const [n, setN] = useState(0);\n  return <button onClick={() => setN(n + 1)}>{n}</button>;\n}\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P7-use-client" in result.stderr


def test_use_client_is_not_asked_of_a_project_that_is_not_next(enforcing):
    """It is a Next.js directive; requiring it in a Vite app would be requiring
    a mistake."""
    _records(enforcing, _design("portal/**"))
    _write(enforcing, "portal/components/Counter.tsx",
           "import { useState } from 'react';\n\nexport function Counter() {\n"
           "  const [n, setN] = useState(0);\n  return <button onClick={() => setN(n + 1)}>{n}</button>;\n}\n")

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_a_provider_sdk_outside_the_gateway_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", "import anthropic\n\nclient = anthropic.Anthropic()\n")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P10-gateway" in result.stderr and "anthropic" in result.stderr


def test_the_gateway_is_where_the_sdk_belongs(enforcing):
    """The gateway's own modules are part of the rule, not an allowlist entry:
    one rule, written once."""
    _records(enforcing, _design("runtime/**"))
    _write(enforcing, "runtime/llm_gateway.py", "import anthropic\n\nclient = anthropic.Anthropic()\n")

    assert _commit(enforcing, MESSAGE).returncode == 0


# Assembled rather than written out: this file is scanned like any other, and a
# `not-a-secret:` marker here would travel into the file the test writes and
# exempt the very line it is proving gets caught.
SECRET_LINE = 'TOKEN = "sk-' + 'ant-abcdefghijklmnopqrstuvwxyz0123456789"\n'


def test_a_credential_shaped_string_is_refused(enforcing):
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", SECRET_LINE)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P12-secrets" in result.stderr


def test_a_line_that_has_to_hold_one_says_so(enforcing):
    """A redaction test must contain the string it proves gets scrubbed."""
    _records(enforcing)
    _write(enforcing, "scripts/tool.py", SECRET_LINE.rstrip("\n") + "  # not-a-secret: redaction fixture\n")

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_the_secrets_check_reads_test_files_too(enforcing):
    """Unlike the code-shape checks: a real key committed in a test is leaked
    exactly as far as one in a module."""
    _records(enforcing, TESTS_DESIGN)
    _write(enforcing, "scripts/test/test_thing.py", SECRET_LINE)

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P12-secrets" in result.stderr


LOCK = "certifi==2024.2.2 \\\n    --hash=sha256:aaa\n"


def _lock(repo, *packages: str) -> None:
    _write(repo, "requirements.lock", "".join(f"{p} \\\n    --hash=sha256:aaa\n" for p in packages))


def test_a_package_the_design_does_not_name_is_refused(enforcing):
    _lock(enforcing, "certifi==2024.2.2")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a lock file", "--no-verify")
    _records(enforcing, _design("requirements*.lock"))
    _lock(enforcing, "certifi==2024.2.2", "tenacity==8.2.3")

    result = _commit(enforcing, MESSAGE)

    assert result.returncode != 0
    assert "P2-dependencies" in result.stderr and "tenacity" in result.stderr


def test_a_package_the_design_names_passes(enforcing):
    _lock(enforcing, "certifi==2024.2.2")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a lock file", "--no-verify")
    _records(enforcing, _design("requirements*.lock").replace(
        "## Dependencies\nnone", "## Dependencies\n- `tenacity` 8.2.3 — the retry ladder; no transitive additions"))
    _lock(enforcing, "certifi==2024.2.2", "tenacity==8.2.3")

    assert _commit(enforcing, MESSAGE).returncode == 0


def test_removing_a_package_is_not_an_addition(enforcing):
    _lock(enforcing, "certifi==2024.2.2", "tenacity==8.2.3")
    _git(enforcing, "add", "-A")
    _git(enforcing, "commit", "-qm", "chore: a lock file", "--no-verify")
    _records(enforcing, _design("requirements*.lock"))
    _lock(enforcing, "certifi==2024.2.2")

    assert _commit(enforcing, MESSAGE).returncode == 0
