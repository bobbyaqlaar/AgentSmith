"""
scripts/test/test_cli_approve.py — `agentsmith approve`: the only way a rule
deviation becomes allowed (.agent-rfc/designs/governance-enforcement.md, G1).

The record must come from a person at a terminal. Agent shells — Claude Code,
Cursor, Antigravity, Copilot, Gemini, Codex — run commands without a
controlling terminal, so reading the confirmation from /dev/tty is what makes
"ask the owner first" mechanical rather than a matter of trust. Both halves are
tested: refused with no terminal, recorded with one.
"""

from __future__ import annotations

import json
import os
import pty
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import gate_models as gm

from runtime.machine import governance

DESIGN = """---
status: active
scope:
  - src/**
---
# A change

## Problem
p

## Approach
a

## Pillars
- P3 **deviation D1** — see Deviations.

## Deviations
- D1 — P3 — the hooks emit no spans — approval: pending

## Dependencies
none

## Levers
- `gate-integrity` — stated, not hidden.
"""


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    (tmp_path / ".agent-rfc/designs").mkdir(parents=True)
    (tmp_path / ".agent-rfc/designs/change.md").write_text(DESIGN, encoding="utf-8")
    (tmp_path / ".agenticframework").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(tmp_path)], check=True)
    for key, value in (("user.name", "Owner"), ("user.email", "owner@example.com")):
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_on_a_terminal(repo: Path, args: list[str], typed: str) -> tuple[int, str]:
    """Run the CLI with a controlling terminal, as a person's shell has."""
    pid, fd = pty.fork()
    if pid == 0:                                            # child
        os.chdir(repo)
        os.environ["PYTHONPATH"] = str(REPO)                # the framework checkout this test runs from
        os.execv(sys.executable, [sys.executable, "-c",
                                  "import sys; from runtime.cli import main; sys.exit(main())", *args])
    os.write(fd, typed.encode())
    output = b""
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        output += chunk
    return os.waitpid(pid, 0)[1] >> 8, output.decode(errors="replace")


def test_an_agent_shell_cannot_record_an_approval(repo):
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from runtime.cli import main; sys.exit(main())",
         "approve", ".agent-rfc/designs/change.md", "D1", "--statement", "go ahead"],
        capture_output=True, text=True, check=False, cwd=repo, stdin=subprocess.DEVNULL,
        start_new_session=True,                             # no controlling terminal, like an agent's shell
        env=dict(os.environ, PYTHONPATH=str(REPO)),
    )
    assert result.returncode != 0
    assert "terminal" in (result.stderr + result.stdout)
    assert not (repo / gm.APPROVALS_FILE).exists(), "nothing may be written without the owner"


def test_the_owner_at_a_terminal_records_an_approval_the_gate_resolves(repo):
    code, output = _run_on_a_terminal(
        repo, ["approve", ".agent-rfc/designs/change.md", "D1", "--statement", "spans come later"], "D1\n")

    assert code == 0, output
    assert "the hooks emit no spans" in output, "the owner is shown what they are approving"
    [line] = (repo / gm.APPROVALS_FILE).read_text(encoding="utf-8").splitlines()
    record = gm.Approval.model_validate(json.loads(line))
    assert record.deviation == "D1" and record.channel == "tty"
    assert record.approver == "Owner <owner@example.com>"
    assert record.statement == "spans come later"
    assert record.id in output, "the id to paste into the design is printed"

    design = (repo / ".agent-rfc/designs/change.md").read_text(encoding="utf-8").replace("pending", record.id)
    deviations, errors = gm.parse_deviations(design.split("## Deviations")[1].split("## Dependencies")[0])
    assert errors == []
    assert gm.check_approvals(deviations, [record], ".agent-rfc/designs/change.md") == []


def test_typing_the_wrong_confirmation_records_nothing(repo):
    code, output = _run_on_a_terminal(
        repo, ["approve", ".agent-rfc/designs/change.md", "D1", "--statement", "x"], "no\n")
    assert code != 0 and "not approved" in output
    assert not (repo / gm.APPROVALS_FILE).exists()


def test_a_deviation_the_design_does_not_list_cannot_be_approved(repo):
    code, output = _run_on_a_terminal(
        repo, ["approve", ".agent-rfc/designs/change.md", "D7", "--statement", "x"], "D7\n")
    assert code != 0 and "D7" in output and "does not list" in output


def test_design_new_writes_the_skeleton_the_gate_asks_for(repo):
    code = governance.design_new("my-change", ["src/**", "tests/**"], root=repo)
    assert code == 0
    text = (repo / ".agent-rfc/designs/my-change.md").read_text(encoding="utf-8")
    registry = gm.Registry.model_validate_json((REPO / "templates/governance.json").read_text(encoding="utf-8"))
    for section in registry.records.design_sections:
        assert f"## {section}" in text
    for pillar in registry.pillars:
        if "design" in pillar.check:
            assert f"P{pillar.id}" in text and pillar.design_question in text
    assert "src/**" in text and "status: active" in text
    pillars_section = text.split("## Pillars")[1].split("## Deviations")[0]
    import re

    assert not re.search(r"^- P\d+ applies", pillars_section, re.M), \
        "the skeleton must not pre-answer its own pillars"
    assert gm.check_pillars(pillars_section, registry, []), \
        "the gate rejects the skeleton until a person answers it"
    assert governance.design_new("my-change", ["src/**"], root=repo) != 0, "an existing design is never overwritten"
