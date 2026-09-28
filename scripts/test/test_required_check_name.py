"""
scripts/test/test_required_check_name.py — the name branch protection requires is
the name the workflow reports.

`main` requires the check `Process gates (design + review)` (enabled 2026-09-29,
.agent-rfc/designs/branch-protection-enabled.md). GitHub matches a required check
by that exact string against the job's reported name. Renaming the job in
.github/workflows/self-test.yml would not fail anything: the renamed job reports
under its new name, the required check never arrives, and every push sits blocked
on a check that cannot come — or, with the admin exemption, sails past a
protection that is no longer matching anything.

Nothing connected the two, so this pins them: the job's `name:`, and the string
docs/process-gates.md tells a reader is required. Changing either alone fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "self-test.yml"
GATES_DOC = REPO / "docs" / "process-gates.md"

# The string configured on the branch. Changing it here is not enough: it has to
# be changed on GitHub too, which is why the docstring says where it lives.
REQUIRED_CHECK = "Process gates (design + review)"


def test_the_gate_job_reports_under_the_required_name():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job = workflow["jobs"]["process-gates"]
    assert job["name"] == REQUIRED_CHECK, (
        f"branch protection on main requires {REQUIRED_CHECK!r}; this job reports as "
        f"{job['name']!r}, so the required check would never arrive"
    )


def test_the_docs_name_the_same_required_check():
    """A reader who has to re-apply the protection needs the exact string, and a
    near-miss in prose is not detectable by reading."""
    assert REQUIRED_CHECK in GATES_DOC.read_text(), (
        f"docs/process-gates.md does not name the required check exactly as "
        f"{REQUIRED_CHECK!r} — the one place a reader would copy it from"
    )


def test_the_job_name_is_not_generated_from_something_else():
    """Guards the test above: a `name:` built from an expression would make the
    comparison vacuous, since the file would hold the template, not the name."""
    assert not re.search(r"\$\{\{", yaml.safe_load(WORKFLOW.read_text())["jobs"]["process-gates"]["name"]), \
        "the job name is templated, so this file does not determine what GitHub sees"
