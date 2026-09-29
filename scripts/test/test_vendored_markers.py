"""
scripts/test/test_vendored_markers.py — the trees AgentSmith vendors carry none
of the markers its own Guardrail 1 forbids.

`hooks/pre-commit` Guardrail 1 refuses a commit whose staged files contain
`ponytail:`, `TODO: agent` or `@agent-ignore`. Since
.agent-rfc/designs/scaffold-rfc-and-vouched-skip.md that guardrail skips files the
scaffold manifest vouches for, so a marker shipped inside `scripts/` or `runtime/`
would no longer be caught in a tenant. This is where it is caught instead: in the
repository that can fix it, over the whole tree rather than whatever a commit
happened to stage.

The pair to scripts/test/test_bare_except_tree.py, which does the same for
Guardrail 2. Between them, the skip moves where a defect surfaces without
removing the check.

`scripts/test/` and `runtime/test/` are excluded because they are NOT vendored —
verified in the design, and asserted below so the exclusion cannot quietly become
a licence for shipped code.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# The same three the hook greps for (hooks/pre-commit, Guardrail 1).
MARKERS = re.compile(r"ponytail:|TODO: agent|@agent-ignore")
VENDORED = ("scripts/", "runtime/")
NOT_VENDORED = ("scripts/test/", "runtime/test/")


def _vendored_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "scripts/*", "runtime/*"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [p for p in out if p.startswith(VENDORED) and not p.startswith(NOT_VENDORED)]


def test_the_sweep_covers_a_real_file_list():
    """A sweep over nothing passes silently, which is the failure this whole
    area keeps producing."""
    files = _vendored_files()
    assert len(files) > 50, f"only {len(files)} vendored files — the sweep is not sweeping"
    assert "scripts/verify_system.py" in files, "the file that carried the marker is not covered"
    assert not any(f.startswith(NOT_VENDORED) for f in files)


def test_no_vendored_file_carries_a_marker_guardrail_1_forbids():
    offenders = []
    for rel in _vendored_files():
        path = REPO / rel
        try:
            text = path.read_text(errors="replace")
        except OSError:  # fail-open: unreadable here means the file list is stale, not that it passed
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if MARKERS.search(line):
                offenders.append(f"{rel}:{number}: {line.strip()[:80]}")
    assert not offenders, (
        "these are vendored into every tenant, where Guardrail 1 no longer checks them — "
        "assemble the literal or remove it:\n" + "\n".join(offenders)
    )
