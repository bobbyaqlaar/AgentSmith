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

from test_process_gate import REPO, _ci, _git, _write, needs_git

import gate_models as gm
import process_gate as pg

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
            {"id": "review_log", "path": "docs/REVIEW_LOG.md", "patterns": ["*REVIEW*.md"], "append_only": True},
            {"id": "archive", "path": None, "patterns": ["*ARCHIVE*.md"], "required": False, "append_only": True},
            {"id": "user_manual", "path": None, "patterns": [], "required": False},
            {"id": "changelog", "path": None, "patterns": ["CHANGELOG*.md"], "required": False, "append_only": True},
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


# ── what a pointer may name (option (a): look in the target) ─────────────────
#
# Unit tests on the verdict, with the target documents written here: whether a
# number is a name or a position is a property of the document it points into.

RECORDS = gm.Artifacts(types=[
    gm.Artifact(id="archive", path="docs/PRODUCT_ARCHIVE.md", append_only=True),
    gm.Artifact(id="changelog", path="CHANGELOG.md", append_only=True),
    gm.Artifact(id="design", path="docs/DESIGN.md"),
])
DOCS = {
    "docs/PRODUCT_ARCHIVE.md": (
        "# Archive\n\n## P10 — Pillars in CI\n\n"
        "| 4.14 | Session revocation | `revoked_sessions` |\n"
        "| ~~5.10~~ | ~~`<org>` placeholder~~ | Done |\n"
        "| P10a (Pillar 2) | map_codebase.py never invoked |\n\n"
        "- **2.3 HITL blob I/O errors:** a missing key raises.\n\n"
        "```bash\n# the graph, rebuilt (4.13)\n```\n"
    ),
    "CHANGELOG.md": "# Changelog\n\n## [1.1.0] — 2026-07-29\n",
    "docs/DESIGN.md": (
        "# Design\n\n## 5.10 Numbered heading\n\n## 2. Strict Bias\n\n"
        "| 2 | Bias & fairness | Partial |\n\n## G3 — the sweep\n\n#### E.1 — Setup\n"
    ),
    "docs/a/c.md": "# C\n\n| R4 | an item |\n",
}


def _xref(line: str, source: str = "README.md", records=RECORDS) -> list:
    return pg.cross_reference_problems([(source, line)], DOCS.get, records)


@pytest.mark.parametrize("line", [
    "the entry `docs/PRODUCT_ARCHIVE.md 4.14`",            # a table row's ID in an append-only record
    "see docs/PRODUCT_ARCHIVE.md 5.10.",                    # struck through, still the entry's ID
    "(docs/PRODUCT_ARCHIVE.md P10a)",                       # a non-numeric ID
    "docs/PRODUCT_ARCHIVE.md 2.3: a missing key is logged",  # a list item's bold lead
    "`CHANGELOG.md` 1.1.0 (what the review found)",         # a release, behind a backtick
    "docs/DESIGN.md § G3",                                  # a non-numeric name in a living doc  <!-- xref: example -->
    "`DEVLOG.md` 2026-09-12",                               # a date, not a pointer
])
def test_a_pointer_to_a_name_the_target_defines_passes(line):
    assert _xref(line) == []


# In order: a line number; a numbered heading; a numbered heading that a table
# row repeats; a lettered part's numbering; a number only a code block holds;
# a number that is only part of a defined one (4.14); a document not in the repo.
@pytest.mark.parametrize("line, why", [
    ("see docs/DESIGN.md#L120", "line number"),  # <!-- xref: example -->
    ("see docs/DESIGN.md 5.10", "not a name"),  # <!-- xref: example -->
    ("see `docs/DESIGN.md` §2", "not a name"),  # <!-- xref: example -->
    ("see docs/DESIGN.md E.1", "not a name"),  # <!-- xref: example -->
    ("see docs/PRODUCT_ARCHIVE.md 4.13", "not a name"),  # <!-- xref: example -->
    ("see docs/PRODUCT_ARCHIVE.md 4.1", "not a name"),  # <!-- xref: example -->
    ("`docs/UserManual.md` §2.3b and Part E", "not in this repo"),  # <!-- xref: example -->
])
def test_a_pointer_to_anything_else_is_refused(line, why):
    problems = _xref(line)
    assert len(problems) == 1 and why in problems[0], problems


def test_a_target_is_found_beside_the_line_first():
    assert _xref("c.md R4", source="docs/a/b.md") == []  # <!-- xref: example -->
    assert "not in this repo" in _xref("c.md R4", source="docs/b.md")[0]  # <!-- xref: example -->


def test_without_a_registry_every_document_is_living():
    """The stricter reading: nothing is append-only unless the registry says so."""
    assert "not a name" in _xref("docs/PRODUCT_ARCHIVE.md 4.14", records=None)[0]
    assert _xref("docs/PRODUCT_ARCHIVE.md P10a", records=None) == []


def test_each_pointer_on_a_line_is_judged():
    line = "docs/DESIGN.md 5.10 and docs/PRODUCT_ARCHIVE.md 4.13, but CHANGELOG.md 1.1.0"  # <!-- xref: example -->
    assert len(_xref(line)) == 2


def test_the_example_marker_still_exempts_a_line():
    assert _xref("never `docs/DESIGN.md#L120` <!-- xref: example -->") == []


def test_added_lines_carry_the_file_they_are_in():
    """A pointer resolves beside its own file, so each line needs its file; and
    a line whose content begins `++` is content, not a diff header."""
    diff = (
        "diff --git a/docs/a.md b/docs/a.md\n--- a/docs/a.md\n+++ b/docs/a.md\n@@ -0,0 +1,2 @@\n"
        "+first\n+++ not a header\n"
        "diff --git a/b.py b/b.py\nnew file mode 100644\n--- /dev/null\n+++ b/b.py\n@@ -0,0 +1 @@\n"
        "+second\n"
    )
    assert pg._added_lines(diff) == [("docs/a.md", "first"), ("docs/a.md", "++ not a header"), ("b.py", "second")]


def test_a_name_in_an_append_only_log_passes_the_commit_gate(repo_with_artifacts):
    """End to end: the registry's `append_only` reaches the commit gate. The
    entry is a numbered row, which is a name only in an append-only document —
    `## Pass 4` would pass anywhere and prove nothing about the registry."""
    _write(repo_with_artifacts, "docs/REVIEW_LOG.md", "# Review log\n\n| 4 | the fourth pass |\n")
    _write(repo_with_artifacts, "docs/DESIGN.md", "# Design\n\nSee docs/REVIEW_LOG.md §4 for the passes.\n")
    _git(repo_with_artifacts, "add", "-A")
    result = _git(repo_with_artifacts, "commit", "-qm", "docs: point at a log entry", check=False)

    assert result.returncode == 0, result.stderr


def test_the_backtick_form_is_refused_by_the_commit_gate(repo_with_artifacts):
    """`portal/README.md` carried this past the old rule: a backtick between the
    file and the `§`."""
    text = "# Design\n\nSee `docs/UserManual.md` §2.3b.\n"  # <!-- xref: example -->
    _write(repo_with_artifacts, "docs/DESIGN.md", text)
    _git(repo_with_artifacts, "add", "-A")
    result = _git(repo_with_artifacts, "commit", "-qm", "docs: a dead pointer", check=False)

    assert result.returncode != 0
    assert "docs/UserManual.md" in result.stderr


def test_ci_reads_the_pointers_of_a_commit_that_touches_no_gated_path(repo_with_artifacts):
    """Documents are mostly ungated. CI and the sweep skipped such a commit
    whole, so a pointer the commit gate would refuse got past both when that
    gate was bypassed."""
    base = _git(repo_with_artifacts, "rev-parse", "HEAD").stdout.strip()
    text = "# Design\n\nSee docs/REVIEW_LOG.md#L4.\n"  # <!-- xref: example -->
    _write(repo_with_artifacts, "docs/DESIGN.md", text)
    _git(repo_with_artifacts, "add", "-A")
    _git(repo_with_artifacts, "commit", "-qm", "docs: sneak a pointer", "--no-verify")

    result = _ci(repo_with_artifacts, base)

    assert result.returncode == 1
    assert "docs: sneak a pointer" in result.stdout and "line number" in result.stdout


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
