"""A new repository's Security job fails, and says that is expected and what to write.

.agent-rfc/designs/first-run-security-message.md. The controls run for real on the
templates `tenant init` really seeds: a copy of the text would pass with the
templates wrong.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import gate_models as gm
from _shared import load_script

from agentsmith.cli import first_push_note

PORT = load_script("security_port")
TEMPLATES = REPO / "fixtures" / "security" / "templates"
RISK = ".agent-rfc/security/risk_register.yaml"
AGENCY = ".agent-rfc/security/agency_manifest.yaml"


def _rows(tmp_path: Path, monkeypatch, replaced: dict[str, str] | None = None) -> dict:
    from agentsmith import conformance

    case = conformance.SecurityCase(name="t", verb="check", expect={"verdict": "pass"}, files={
        RISK: (TEMPLATES / "risk_register.yaml").read_text(encoding="utf-8"),
        AGENCY: (TEMPLATES / "agency_manifest.yaml").read_text(encoding="utf-8"),
        **(replaced or {}),
    })
    root = conformance.build_security_fixture(tmp_path / "repo", case)
    monkeypatch.chdir(root)
    answer = PORT.check(root, gm.SecurityRequest(controls=["SEC-RISK-001", "SEC-AGENCY-001"]))
    return {row.id: row for row in answer.controls}


@pytest.mark.parametrize("control, path, fields", [
    ("SEC-RISK-001", RISK, [name for name, f in gm.RiskEntry.model_fields.items() if f.is_required()]),
    ("SEC-AGENCY-001", AGENCY, [name for name, f in gm.AgencyAction.model_fields.items() if f.is_required()]),
])
def test_a_shipped_template_fails_and_says_where_and_what(tmp_path, monkeypatch, control, path, fields):
    row = _rows(tmp_path, monkeypatch)[control]
    assert row.result == "fail", "expected explains a red job and never turns it green"
    assert path in row.message and str(tmp_path) not in row.message, row.message
    assert "A new repository starts here" in row.message
    assert [name for name in fields if name not in row.message] == [], row.message


def test_replacing_both_templates_is_the_way_to_green(tmp_path, monkeypatch):
    """What the templates and messages tell a reader to write."""
    rows = _rows(tmp_path, monkeypatch, {
        RISK: "version: 1\nentries:\n  - id: RISK-001\n    description: A bad deploy.\n    severity: medium\n"
              "    mitigations: [Staging first.]\n    control_ids: [SEC-RISK-001]\n",
        AGENCY: "version: 1\nactions:\n  - workflow: cd-production\n    action: deploy_to_production\n"
                "    needs_hitl: true\n",
    })
    assert {row.id: row.result for row in rows.values()} == {"SEC-RISK-001": "pass", "SEC-AGENCY-001": "pass"}


def test_the_shipped_templates_still_carry_what_the_controls_detect():
    assert "RISK-EXAMPLE-001" in (TEMPLATES / "risk_register.yaml").read_text(encoding="utf-8")
    assert "- workflow: example_workflow" in (TEMPLATES / "agency_manifest.yaml").read_text(encoding="utf-8")


@pytest.mark.parametrize("written, named, absent", [
    ([RISK, AGENCY, "README.md"], [RISK, "SEC-RISK-001", AGENCY, "SEC-AGENCY-001"], []),
    ([RISK], [RISK, "SEC-RISK-001"], [AGENCY]),
])
def test_the_note_names_only_what_this_run_seeded(written, named, absent):
    note = first_push_note(written)
    assert "expected" in note and "bash .githooks/process-gate security check" in note
    assert [text for text in named if text not in note] == []
    assert [text for text in absent if text in note] == []


def test_no_note_when_nothing_graded_was_seeded():
    assert first_push_note(["README.md"]) == ""


def _init(root: Path, home: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-m", "agentsmith.cli", "tenant", "init", "demo-app", "--stack", "python-fastapi",
         "--root", str(root)],
        cwd=REPO, capture_output=True, text=True, check=False,
        env={**os.environ, "AGENTSMITH_DIR": str(REPO), "HOME": str(home)},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def test_init_says_it_last_and_only_once(tmp_path):
    root, home = tmp_path / "tenant", tmp_path / "home"
    root.mkdir()
    home.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    printed = _init(root, home)
    assert printed.rstrip().endswith("bash .githooks/process-gate security check"), printed[-400:]
    assert printed.index("git add -A && git commit") < printed.index("Your first push will fail")
    assert "Your first push" not in _init(root, home), "the placeholders were seeded by the earlier run"
