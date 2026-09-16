"""
scripts/test/test_gate_artifacts.py — G5a: one artifact per type, and
cross-references that do not rot.

A repo grows a second backlog, a third review file and four READMEs, and then
no agent knows which one governs: OTS had two READMEs, two `CRITICAL_REVIEW_*`,
a TODO plan, 22 specs and 31 plans. The registry names one file per type; the
check fails on a second one, and on a tracked Markdown file that is neither an
artifact nor declared reference documentation.

The cross-reference rule travels with it: a pointer into another document's
section numbers (`SPECS.md §23`) is stale the next time that document is
edited. It is checked on the lines a commit ADDS, so adopting the rule does not
fail every existing pointer — those go as each document is migrated (G5b).

Both are governed by one per-repo mode, because the documents move in G5b and a
repo that has not migrated yet must not be blocked on files it cannot delete.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, _git, _write, needs_git

pytestmark = needs_git


def _artifacts(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "process_gate.py"), "artifacts", *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def _set_mode(repo: Path, mode: str, **extra) -> None:
    """The repo's own config: which mode, and any `extends.artifacts` layout."""
    config = json.loads((repo / ".agenticframework" / "process-gates.json").read_text(encoding="utf-8"))
    config["artifacts"] = mode
    config.setdefault("extends", {}).update(extra)
    (repo / ".agenticframework" / "process-gates.json").write_text(json.dumps(config, indent=2) + "\n")


LAYOUT = {
    "artifacts": {
        "types": [
            {"id": "readme", "path": "README.md", "patterns": ["README*.md", "docs/README*.md"]},
            {"id": "backlog", "path": "docs/PRODUCT_BACKLOG.md", "patterns": ["*BACKLOG*.md", "*TODO*.md"]},
            {"id": "design", "path": "docs/DESIGN.md", "patterns": ["SPECS*.md", "*DESIGN*.md"]},
            {"id": "review_log", "path": "docs/REVIEW_LOG.md", "patterns": ["*REVIEW*.md"]},
            {"id": "archive", "path": None, "patterns": ["*ARCHIVE*.md"], "required": False},
            {"id": "user_manual", "path": None, "patterns": [], "required": False},
            {"id": "changelog", "path": None, "patterns": ["CHANGELOG*.md"], "required": False},
            {"id": "test_script", "path": None, "patterns": [], "required": False},
        ],
        "reference": ["docs/reference/*.md", ".agent-rfc/**/*.md"],
        "ignored": [],
    }
}


@pytest.fixture()
def repo_with_artifacts(gated_repo):
    """A repo whose layout is the four artifacts it declares."""
    for path in ("README.md", "docs/PRODUCT_BACKLOG.md", "docs/DESIGN.md", "docs/REVIEW_LOG.md"):
        _write(gated_repo, path, f"# {Path(path).stem}\n")
    _set_mode(gated_repo, "enforce", **LAYOUT)
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "docs: the four artifacts", "--no-verify")
    return gated_repo


# ── one file per type ────────────────────────────────────────────────────────


def test_a_repo_with_exactly_its_artifacts_passes(repo_with_artifacts):
    result = _artifacts(repo_with_artifacts)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_second_file_of_a_type_is_named_with_the_one_that_governs(repo_with_artifacts):
    _write(repo_with_artifacts, "docs/TODO-implementation-plan.md", "# plan\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: a second backlog", "--no-verify")

    result = _artifacts(repo_with_artifacts)

    assert result.returncode != 0
    assert "docs/TODO-implementation-plan.md" in result.stdout
    assert "docs/PRODUCT_BACKLOG.md" in result.stdout, "it must name the file that governs"


def test_a_markdown_file_that_is_neither_artifact_nor_reference_is_reported(repo_with_artifacts):
    _write(repo_with_artifacts, "docs/notes-from-a-call.md", "# notes\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: stray", "--no-verify")

    result = _artifacts(repo_with_artifacts)

    assert result.returncode != 0
    assert "docs/notes-from-a-call.md" in result.stdout


def test_declared_reference_documentation_is_not_a_stray(repo_with_artifacts):
    """Shipped product docs are not project records: a tenant reads them."""
    _write(repo_with_artifacts, "docs/reference/how-the-gate-works.md", "# shipped doc\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: reference", "--no-verify")

    assert _artifacts(repo_with_artifacts).returncode == 0


def test_a_missing_required_artifact_fails_and_an_optional_one_does_not(repo_with_artifacts):
    (repo_with_artifacts / "docs" / "REVIEW_LOG.md").unlink()
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: drop the review log", "--no-verify")

    result = _artifacts(repo_with_artifacts)

    assert result.returncode != 0
    assert "docs/REVIEW_LOG.md" in result.stdout and "missing" in result.stdout.lower()
    assert "changelog" not in result.stdout.lower(), "an optional type this repo does not have is not missing"


# ── the mode ─────────────────────────────────────────────────────────────────


def test_report_mode_says_what_would_fail_without_failing(repo_with_artifacts):
    """AgentSmith and OTS run in report until G5b moves their documents; a check
    that blocked before the migration would block the migration."""
    _set_mode(repo_with_artifacts, "report", **LAYOUT)
    _write(repo_with_artifacts, "SPECS.md", "# a second design doc\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: second design", "--no-verify")

    result = _artifacts(repo_with_artifacts)

    assert result.returncode == 0, result.stdout
    assert "SPECS.md" in result.stdout
    assert "report" in result.stdout.lower()


def test_off_is_the_default_and_checks_nothing(gated_repo):
    """The fixture carries AgentSmith's own config, which declares a mode; the
    default is what a repo that has declared nothing gets."""
    config_path = gated_repo / ".agenticframework" / "process-gates.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.pop("artifacts", None)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    _write(gated_repo, "docs/ONE-MORE-BACKLOG.md", "# no registry adopted here\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "docs: stray", "--no-verify")

    result = _artifacts(gated_repo)

    assert result.returncode == 0
    assert "off" in result.stdout.lower()


# ── cross-references ─────────────────────────────────────────────────────────


def test_a_new_line_pointing_at_another_documents_section_number_is_refused(repo_with_artifacts):
    _write(repo_with_artifacts, "docs/DESIGN.md", "# Design\n\nSee docs/REVIEW_LOG.md §4 for the passes.\n")
    _git(repo_with_artifacts, "add", "-A")
    result = _git(repo_with_artifacts, "commit", "-qm", "docs: point at a section number", check=False)

    assert result.returncode != 0
    assert "§" in result.stderr or "section number" in result.stderr


def test_an_existing_pointer_is_left_alone_until_its_document_moves(repo_with_artifacts):
    """New and changed lines first: adopting the rule must not fail every
    pointer a repo already has, or no repo can adopt it."""
    _write(repo_with_artifacts, "docs/DESIGN.md", "# Design\n\nSee docs/REVIEW_LOG.md §4 for the passes.\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: legacy pointer", "--no-verify")

    _write(repo_with_artifacts, "docs/DESIGN.md",
           "# Design\n\nSee docs/REVIEW_LOG.md §4 for the passes.\n\nA new line with no pointer.\n")
    _git(repo_with_artifacts, "add", "-A")
    result = _git(repo_with_artifacts, "commit", "-qm", "docs: add a line", check=False)

    assert result.returncode == 0, result.stderr


def test_a_quoted_example_carries_a_marker(repo_with_artifacts):
    """The rule's own documentation has to be able to show a bad pointer."""
    _write(repo_with_artifacts, "docs/DESIGN.md",
           "# Design\n\nNever write `SPECS.md §23` — numbers move. <!-- xref: example -->\n")
    _git(repo_with_artifacts, "add", "-A")
    result = _git(repo_with_artifacts, "commit", "-qm", "docs: explain the rule", check=False)

    assert result.returncode == 0, result.stderr


def test_a_heading_name_is_a_fine_reference(repo_with_artifacts):
    _write(repo_with_artifacts, "docs/DESIGN.md", "# Design\n\nSee docs/REVIEW_LOG.md, section Sign-off.\n")
    _git(repo_with_artifacts, "add", "-A")
    result = _git(repo_with_artifacts, "commit", "-qm", "docs: name the heading", check=False)

    assert result.returncode == 0, result.stderr


# ── the framework's own registry ─────────────────────────────────────────────


def test_the_shipped_registry_names_one_path_per_type() -> None:
    registry = json.loads((REPO / "templates" / "governance.json").read_text(encoding="utf-8"))
    paths = [a["path"] for a in registry["artifacts"]["types"] if a.get("path")]
    assert len(paths) == len(set(paths)), "two types cannot claim the same file"
    assert {"readme", "backlog", "archive", "design", "review_log"} <= {
        a["id"] for a in registry["artifacts"]["types"]
    }


# ── the sweep carries the same verdict ───────────────────────────────────────


def _sweep(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "process_gate.py"), "sweep"],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def test_the_sweep_reports_artifact_problems_without_blocking_in_report_mode(repo_with_artifacts):
    """`report` has to mean the same thing everywhere it is read: the sweep runs
    at every commit, push, session start and turn end, so a sweep that blocked
    would block the repo that is still consolidating."""
    _set_mode(repo_with_artifacts, "report", **LAYOUT)
    _write(repo_with_artifacts, "SPECS.md", "# a second design doc\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: second design", "--no-verify")

    result = _sweep(repo_with_artifacts)

    assert result.returncode == 0, result.stdout
    assert "SPECS.md" in result.stdout


def test_the_sweep_fails_on_artifact_problems_in_enforce_mode(repo_with_artifacts):
    _write(repo_with_artifacts, "SPECS.md", "# a second design doc\n")
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: second design", "--no-verify")

    result = _sweep(repo_with_artifacts)

    assert result.returncode != 0
    assert "SPECS.md" in result.stdout
