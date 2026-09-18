"""
scripts/test/test_scaffold_review.py — a new tenant's first commit
(.agent-rfc/designs/tenant-architecture.md).

`tenant init` arms the design and review gates, so its own scaffold needs a
design and a review. It writes the design; the review is `n/a: generated
scaffold`, which the gate accepts only on the root commit and only when every
gated file is byte-for-byte what `tenant init` wrote. These tests commit a real
scaffold through the real hooks.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, needs_git

pytestmark = needs_git

FIRST_COMMIT = [
    "-m", "chore: scaffold acme",
    "-m", "Design: .agent-rfc/designs/scaffold.md",
    "-m", "Review: n/a: generated scaffold",
]


@pytest.fixture()
def scaffold(tmp_path, monkeypatch):
    """An empty repo, scaffolded as a hexagonal agentic tenant."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "tenant"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    sys.path.insert(0, str(REPO))
    from runtime.cli import init_tenant

    init_tenant("acme", root, stack="python-fastapi", architecture="clean", agentic=True)
    return root


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                          capture_output=True, text=True, check=False)


def _commit(root: Path, *message: str) -> subprocess.CompletedProcess:
    _git(root, "add", "-A")
    return _git(root, "commit", *message)


def test_the_untouched_scaffold_goes_in_as_the_first_commit(scaffold):
    result = _commit(scaffold, *FIRST_COMMIT)

    assert result.returncode == 0, result.stderr
    assert "generated scaffold" in result.stdout + result.stderr, "the escape is a visible note, not silence"


def test_the_scaffold_records_its_architecture(scaffold):
    design = (scaffold / "docs" / "DESIGN.md").read_text()
    assert "Hexagonal" in design and "## The agent layer" in design
    manifest = json.loads((scaffold / ".agenticframework" / "scaffold.json").read_text())
    assert manifest["architecture"] == "hexagonal" and manifest["agentic"] is True
    assert ".githooks/commit-msg" in manifest["files"]
    config = json.loads((scaffold / ".agenticframework" / "process-gates.json").read_text())
    assert any("Hexagonal" in line for line in config["extends"]["session_start"])


def test_an_edited_scaffold_file_needs_a_real_review(scaffold):
    workflow = next((scaffold / ".github" / "workflows").glob("ci-*.yml"))
    workflow.write_text(workflow.read_text() + "\n# changed by hand\n")

    result = _commit(scaffold, *FIRST_COMMIT)

    assert result.returncode != 0
    assert workflow.name in result.stderr and "not what" in result.stderr


def test_code_added_to_the_first_commit_needs_a_real_review(scaffold):
    (scaffold / "app").mkdir(exist_ok=True)
    (scaffold / "app" / "main.py").write_text("print(1)\n")

    result = _commit(scaffold, *FIRST_COMMIT)

    assert result.returncode != 0
    assert "app/main.py is not part of the scaffold" in result.stderr, result.stderr


def test_a_file_the_tenant_already_had_is_not_vouched_for(tmp_path, monkeypatch):
    """The manifest lists what `tenant init` wrote, not what it found: code
    that was there before the scaffold is the tenant's, and needs a review."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "existing"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("print('already here')\n")
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    sys.path.insert(0, str(REPO))
    from runtime.cli import init_tenant

    init_tenant("acme", root, stack="python-fastapi", architecture="layered")
    manifest = json.loads((root / ".agenticframework" / "scaffold.json").read_text())
    assert "app/main.py" not in manifest["files"]

    result = _commit(root, *FIRST_COMMIT)

    assert result.returncode != 0 and "app/main.py is not part of the scaffold" in result.stderr


def test_a_later_commit_cannot_claim_to_be_the_scaffold(scaffold):
    assert _commit(scaffold, *FIRST_COMMIT).returncode == 0
    (scaffold / "app").mkdir(exist_ok=True)
    (scaffold / "app" / "main.py").write_text("print(1)\n")

    result = _commit(scaffold, *FIRST_COMMIT)

    assert result.returncode != 0
    assert "first commit" in result.stderr


def test_without_the_manifest_there_is_nothing_to_verify(scaffold):
    (scaffold / ".agenticframework" / "scaffold.json").unlink()

    result = _commit(scaffold, *FIRST_COMMIT)

    assert result.returncode != 0
    assert "scaffold.json" in result.stderr


def test_the_scaffold_design_authorises_no_later_edit(scaffold):
    """It is `done`: the next change to gated code needs a design of its own."""
    assert _commit(scaffold, *FIRST_COMMIT).returncode == 0
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(scaffold / "app" / "logic.py")},
                          "cwd": str(scaffold)})
    result = subprocess.run(["bash", str(scaffold / ".githooks" / "process-gate"), "pre-edit", "--ide", "claude"],
                            input=payload, capture_output=True, text=True, cwd=scaffold, check=False)

    assert '"deny"' in result.stdout


def test_ci_reaches_the_same_verdict_on_the_root_commit(scaffold, tmp_path):
    assert _commit(scaffold, *FIRST_COMMIT).returncode == 0
    head = _git(scaffold, "rev-parse", "HEAD").stdout.strip()
    out = tmp_path / "record.json"

    result = subprocess.run([sys.executable, str(REPO / "scripts" / "process_gate.py"), "ci", "--base", "",
                             "--head", head, "--json", str(out)], cwd=scaffold, capture_output=True, text=True,
                            check=False)

    assert result.returncode == 0, result.stdout
    [record] = json.loads(out.read_text())["commits"]
    assert record["verdict"] == "passed_with_notes"
    assert any("generated scaffold" in note for note in record["notes"])
