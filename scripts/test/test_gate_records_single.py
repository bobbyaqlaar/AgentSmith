"""
scripts/test/test_gate_records_single.py — G5a: `records: single`.

One artifact per type means the design and review records stop being a
directory of files: a change is `## Active change: <slug>` in `docs/DESIGN.md`,
and its review is `## <slug> — Pass N — findings: K` entries in
`docs/REVIEW_LOG.md`. Trailers name `docs/DESIGN.md#<slug>`.

The rules do not change with the shape — the same pillars, deviations,
dependencies, passes and sign-off — so the gate normalises a section into the
shape the legacy checkers already read rather than growing a second set of
them (`no-copy-paste`). These tests are what pin that the rules survive the
move, and that a repo is held to exactly one of the two conventions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import DESIGN_PILLARS, SIGNOFF, _commit, _git, _write, needs_git

pytestmark = needs_git

SLUG = "worker-retry"

GOVERNANCE = f"""## Active change: {SLUG}

```governance
status: active
scope:
  - scripts/lib/**
  - scripts/tool.py
```

### Problem

The worker gives up on the first failure.

### Approach

Retry with a bounded ladder.

### Pillars

- {DESIGN_PILLARS} applies — each was worked for this change.

### Deviations

none

### Dependencies

None added.

### Levers

- `when-the-fallback-fails` — each rung's own failure path is designed.
"""

DESIGN_DOC = "# Design\n\nThe living picture of the system.\n\n" + GOVERNANCE

REVIEW_DOC = f"""# Review log

Append-only.

## {SLUG} — Pass 1 — findings: 1

- `gate-integrity` — the retry had no ceiling; fixed.

## {SLUG} — Pass 2 — findings: 0

Every lever again over the final tree.

## {SLUG} — Sign-off

```
{SIGNOFF.split("```", 2)[1].strip()}
```
"""

MESSAGE = (
    "feat: retry the worker\n\n"
    f"Design: docs/DESIGN.md#{SLUG}\n"
    f"Review: docs/REVIEW_LOG.md#{SLUG}\n"
)


@pytest.fixture()
def single_repo(gated_repo):
    """A repo that keeps its records in the two artifacts."""
    config_path = gated_repo / ".agenticframework" / "process-gates.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["records"] = "single"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    _write(gated_repo, "docs/DESIGN.md", DESIGN_DOC)
    _write(gated_repo, "docs/REVIEW_LOG.md", "# Review log\n\nAppend-only.\n")
    _git(gated_repo, "add", "-A")
    _git(gated_repo, "commit", "-qm", "docs: the two record artifacts", "--no-verify")
    return gated_repo


def _hook_stdout(repo: Path, command: str, payload: dict) -> str:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "process_gate.py"), command],
        cwd=repo, input=json.dumps(payload), capture_output=True, text=True, check=False,
    ).stdout


# ── a change recorded in the two artifacts ───────────────────────────────────


def test_a_commit_whose_records_live_in_the_artifacts_passes(single_repo):
    _write(single_repo, "scripts/tool.py", "print('retry')\n")
    _write(single_repo, "docs/REVIEW_LOG.md", REVIEW_DOC)

    result = _commit(single_repo, MESSAGE)

    assert result.returncode == 0, result.stderr


def test_the_section_must_answer_the_pillars_like_any_design(single_repo):
    answered = f"- {DESIGN_PILLARS} applies — each was worked for this change."
    _write(single_repo, "docs/DESIGN.md", DESIGN_DOC.replace(answered, "- P1 applies — it does"))
    _write(single_repo, "docs/REVIEW_LOG.md", REVIEW_DOC)
    _write(single_repo, "scripts/tool.py", "print('retry')\n")

    result = _commit(single_repo, MESSAGE)

    assert result.returncode != 0
    assert "P2" in result.stderr, result.stderr


def test_the_review_entries_must_end_at_zero_findings(single_repo):
    _write(single_repo, "docs/REVIEW_LOG.md", REVIEW_DOC.replace("Pass 2 — findings: 0", "Pass 2 — findings: 3"))
    _write(single_repo, "scripts/tool.py", "print('retry')\n")

    result = _commit(single_repo, MESSAGE)

    assert result.returncode != 0
    assert "3 finding" in result.stderr


def test_another_slugs_entries_do_not_vouch_for_this_change(single_repo):
    """One log holds every change's passes; they are selected by slug, or a
    clean review of something else would pass this one."""
    _write(single_repo, "docs/REVIEW_LOG.md", REVIEW_DOC.replace(SLUG, "some-other-change"))
    _write(single_repo, "scripts/tool.py", "print('retry')\n")

    result = _commit(single_repo, MESSAGE)

    assert result.returncode != 0, result.stdout


# ── one convention per repo ──────────────────────────────────────────────────


def test_a_legacy_trailer_is_refused_where_records_are_single(single_repo):
    _write(single_repo, "scripts/tool.py", "print('retry')\n")
    _write(single_repo, "docs/REVIEW_LOG.md", REVIEW_DOC)

    result = _commit(single_repo, MESSAGE.replace(f"docs/DESIGN.md#{SLUG}", ".agent-rfc/designs/change.md"))

    assert result.returncode != 0
    assert "docs/DESIGN.md#" in result.stderr


def test_a_single_trailer_is_refused_where_records_are_legacy(gated_repo):
    _write(gated_repo, "scripts/tool.py", "print('retry')\n")

    result = _commit(gated_repo, MESSAGE)

    assert result.returncode != 0
    assert ".agent-rfc/designs" in result.stderr


# ── the edit gate reads the same sections ────────────────────────────────────


def test_an_active_section_unlocks_the_paths_in_its_scope(single_repo):
    payload = {"cwd": str(single_repo), "tool_name": "Edit",
               "tool_input": {"file_path": str(single_repo / "scripts" / "tool.py")}}
    assert _hook_stdout(single_repo, "pre-edit", payload).strip() == ""


def test_a_done_section_unlocks_nothing(single_repo):
    _write(single_repo, "docs/DESIGN.md", DESIGN_DOC.replace("status: active", "status: done"))
    payload = {"cwd": str(single_repo), "tool_name": "Edit",
               "tool_input": {"file_path": str(single_repo / "scripts" / "tool.py")}}

    assert "deny" in _hook_stdout(single_repo, "pre-edit", payload)


def test_session_start_lists_the_active_section(single_repo):
    context = _hook_stdout(single_repo, "session-start", {"cwd": str(single_repo)})
    assert SLUG in context
