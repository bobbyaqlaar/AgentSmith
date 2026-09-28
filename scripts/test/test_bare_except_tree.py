"""
scripts/test/test_bare_except_tree.py — every tracked Python file passes the
repository's own empty-except check.

`hooks/pre-commit` runs `scripts/check_bare_except.py` over the files STAGED in a
commit. That is the whole rule: nothing has ever run it over the tree. For
AgentSmith's own commits it is therefore close to dormant — these files are rarely
staged — and eight unmarked handlers accumulated under it in
`gate_history.py`, `process_gate.py`, `send_dev_record.py`, `map_codebase.py` and
`mutation_check.py`.

They surfaced in the one place that stages everything at once: a tenant's FIRST
commit, where `agentsmith tenant init` has just vendored `scripts/` and `runtime/`
and the printed commit command is refused by the framework's own code
(.agent-rfc/designs/first-commit-guardrail.md).

This is the check that fires on everything, so a new unmarked handler fails here,
where it is written, instead of in a stranger's first commit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "check_bare_except.py"


def _tracked_python_files() -> list[str]:
    # Every tracked .py, with nothing exempt. An earlier version filtered
    # `fixtures/` for "deliberately bad code" \u2014 there is no .py under fixtures/ at
    # all, so the filter matched nothing and only suggested an exemption existed.
    # If a deliberate bad-code fixture is ever added, this failing is the right
    # outcome: someone then decides, rather than inheriting a pre-granted pass.
    return subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "*.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()


def test_the_checker_is_reading_a_real_file_list():
    """Guards the test below: a sweep over nothing passes silently, which is the
    failure mode this whole slice is about."""
    files = _tracked_python_files()
    assert len(files) > 100, f"only {len(files)} tracked .py files — the sweep is not sweeping"
    assert "scripts/process_gate.py" in files


def test_every_tracked_python_file_passes_the_bare_except_check():
    files = _tracked_python_files()
    result = subprocess.run(
        [sys.executable, str(CHECKER), *files],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )
    assert result.returncode == 0, (
        "empty except handlers with no stated reason — append "
        "'# fail-open: <reason>' to the except line, or log or re-raise:\n" + result.stdout + result.stderr
    )
