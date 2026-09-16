"""
scripts/test/test_gate_sweep.py — G3: the bypass sweep.

The commit gate can be skipped: `git commit --no-verify`, a clone whose
`core.hooksPath` was never armed, a rebase, a cherry-pick, or an agent running
git from a shell the IDE does not gate. CI reports it after the push, and on a
plan without branch protection cannot refuse it; the owner ruled out depending
on GitHub anyway.

The sweep is the answer: `process_gate.py sweep` re-checks every commit reachable
locally that has not been verified before, and it runs at the next touchpoint —
pre-commit, pre-push, session start and stop. A bypass therefore survives until
the next thing anyone does in the repo, in any IDE.

Fixtures come from test_process_gate.py: one gated repo shape, not two
(`no-copy-paste`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_process_gate import (  # the gated_repo fixture comes from conftest
    DESIGN,
    MESSAGE,
    REPO,
    REVIEW_CLEAN,
    _commit,
    _git,
    _write,
    needs_git,
)

pytestmark = needs_git


def _sweep(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """The sweep as a hook runs it: the gate script, inside the repo."""
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "process_gate.py"), "sweep", *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def _bypassed_commit(repo: Path, name: str = "scripts/lib/sneaky.py") -> str:
    """A gated commit that never met the commit gate — `--no-verify`."""
    _write(repo, name, "print('no gate')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat: sneak past the gate", "--no-verify")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _designed_commit(repo: Path) -> str:
    _write(repo, "scripts/tool.py", "print(1)\n")
    _write(repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    result = _commit(repo, MESSAGE.replace("feat: x", "feat: add tool"))
    assert result.returncode == 0, result.stderr
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


# ── the verified store ───────────────────────────────────────────────────────


def test_the_first_sweep_initialises_the_pointer_and_says_history_was_not_swept(gated_repo):
    """A repo adopting the sweep has years of commits behind it, none of them
    checked. Sweeping them all would be slow and would fail history that could
    not comply, so the first run records where it started — and says so, rather
    than reporting a clean sweep it never did (`ambiguous-signals`)."""
    result = _sweep(gated_repo)

    assert result.returncode == 0, result.stderr
    assert "not swept" in result.stdout.lower()
    store = json.loads((gated_repo / ".git" / "agentsmith" / "verified").read_text())
    assert _git(gated_repo, "rev-parse", "HEAD").stdout.strip() in store["shas"]


def test_a_second_sweep_with_nothing_new_is_quiet_and_clean(gated_repo):
    _sweep(gated_repo)
    result = _sweep(gated_repo)

    assert result.returncode == 0, result.stderr
    assert "not swept" not in result.stdout.lower()
    assert "nothing new" in result.stdout


# ── catching what skipped the commit gate ────────────────────────────────────


def test_a_no_verify_commit_is_caught_by_the_next_sweep(gated_repo):
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)

    result = _sweep(gated_repo)

    assert result.returncode != 0, result.stdout
    assert sha[:10] in result.stdout
    assert "Design:" in result.stdout or "design" in result.stdout.lower()


def test_a_commit_that_met_the_gate_needs_no_repair(gated_repo):
    _sweep(gated_repo)
    sha = _designed_commit(gated_repo)

    result = _sweep(gated_repo)

    assert result.returncode == 0, result.stdout + result.stderr
    store = json.loads((gated_repo / ".git" / "agentsmith" / "verified").read_text())
    assert sha in store["shas"], "a commit checked clean is not re-checked next time"


def test_a_commit_on_another_local_branch_is_swept_too(gated_repo):
    """`--no-verify` on a side branch is the same bypass. The sweep walks every
    branch reachable locally, not just the one checked out."""
    _sweep(gated_repo)
    _git(gated_repo, "checkout", "-q", "-b", "side")
    sha = _bypassed_commit(gated_repo, "scripts/lib/side.py")
    _git(gated_repo, "checkout", "-q", "main")

    result = _sweep(gated_repo)

    assert result.returncode != 0
    assert sha[:10] in result.stdout


# ── repair ───────────────────────────────────────────────────────────────────


def test_a_repairing_commit_clears_the_bypass(gated_repo):
    """History is never rewritten for the sweep. The fix is a new commit that
    carries the records and names the commits it repairs."""
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)
    assert _sweep(gated_repo).returncode != 0

    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(gated_repo, "scripts/lib/sneaky.py", "print('reviewed now')\n")
    repair = _commit(gated_repo, MESSAGE.replace("feat: x", "fix: bring the bypassed commit under review")
                     + f"Repairs: {sha}\n")
    assert repair.returncode == 0, repair.stderr

    result = _sweep(gated_repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "repaired" in result.stdout


def test_a_repairs_trailer_naming_an_unknown_commit_is_refused(gated_repo):
    """A trailer that names nothing real would let any commit claim a repair."""
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)
    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(gated_repo, "scripts/tool.py", "print(1)\n")
    _commit(gated_repo, MESSAGE.replace("feat: x", "fix: claim a repair") + "Repairs: " + "0" * 40 + "\n")

    result = _sweep(gated_repo)

    assert result.returncode != 0
    assert sha[:10] in result.stdout


# ── where it runs ────────────────────────────────────────────────────────────


def test_pre_commit_refuses_while_a_bypass_is_unrepaired(gated_repo):
    _sweep(gated_repo)
    _bypassed_commit(gated_repo)

    _write(gated_repo, "docs/note.md", "ungated, but the repo is not clean\n")
    result = _commit(gated_repo, "docs: anything")

    assert result.returncode != 0
    assert "sweep" in (result.stdout + result.stderr).lower()


def test_pre_push_refuses_while_a_bypass_is_unrepaired(gated_repo):
    _sweep(gated_repo)
    _bypassed_commit(gated_repo)

    hook = gated_repo / ".githooks" / "pre-push"
    result = subprocess.run(["bash", str(hook)], cwd=gated_repo, input="", capture_output=True, text=True, check=False)

    assert result.returncode != 0
    assert "sweep" in (result.stdout + result.stderr).lower()


def test_the_stop_gate_reports_an_unrepaired_bypass(gated_repo):
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "stop"],
        cwd=gated_repo, input="{}", capture_output=True, text=True, check=False,
    )

    assert '"decision": "block"' in result.stdout
    assert sha[:10] in result.stdout


def test_session_start_names_what_the_sweep_found(gated_repo):
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "session-start"],
        cwd=gated_repo, input="{}", capture_output=True, text=True, check=False,
    )

    assert sha[:10] in result.stdout


# ── the hooks stay armed ─────────────────────────────────────────────────────


def test_the_sweep_rearms_hookspath_and_says_it_did(gated_repo):
    """An unarmed clone is one of the ways a commit skips the gate. Every sweep
    checks, and re-arms where the repo has adopted the gates."""
    _git(gated_repo, "config", "--unset", "core.hooksPath")

    result = _sweep(gated_repo)

    assert _git(gated_repo, "config", "core.hooksPath").stdout.strip() == ".githooks"
    assert "core.hooksPath" in result.stdout


def test_the_sweep_leaves_an_unadopted_repo_alone(tmp_path, monkeypatch):
    """No config, no adoption: the sweep does not arm hooks in a repo that never
    asked for them (the machine-wide git template applies to every repo)."""
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    repo = tmp_path / "plain"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / "a.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: base", "--no-verify")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "process_gate.py"), "sweep"],
        cwd=repo, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0
    assert not _git(repo, "config", "core.hooksPath", check=False).stdout.strip()
    assert "not adopted" in result.stdout


# ── the CLI a person uses ────────────────────────────────────────────────────


def test_gates_repair_lists_the_commits_and_what_each_lacks(gated_repo):
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)

    result = subprocess.run(
        [sys.executable, "-P", "-m", "runtime.cli", "gates", "repair"],
        cwd=gated_repo, capture_output=True, text=True, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": str(gated_repo.parent / "home"),
             "PYTHONPATH": str(REPO), "AGENTSMITH_PYTHON": sys.executable},
    )

    assert result.returncode != 0, result.stdout
    assert sha[:10] in result.stdout
    assert "Repairs:" in result.stdout, "it must say how to fix it, not only what is wrong"


def test_a_repairs_trailer_may_name_a_short_sha(gated_repo):
    """People copy short shas out of `git log`. The trailer is resolved by git,
    which is also what stops a trailer naming something git does not have from
    counting as a repair — the two are the same line of code."""
    _sweep(gated_repo)
    sha = _bypassed_commit(gated_repo)

    _write(gated_repo, ".agent-rfc/designs/change.md", DESIGN)
    _write(gated_repo, ".agent-rfc/reviews/change.md", REVIEW_CLEAN)
    _write(gated_repo, "scripts/lib/sneaky.py", "print('reviewed now')\n")
    repair = _commit(gated_repo, MESSAGE.replace("feat: x", "fix: repair by short sha")
                     + f"Repairs: {sha[:8]}\n")
    assert repair.returncode == 0, repair.stderr

    result = _sweep(gated_repo)

    assert result.returncode == 0, result.stdout
    assert "repaired" in result.stdout


def test_a_long_backlog_of_commits_is_swept_in_batches(gated_repo, monkeypatch):
    """The sweep runs at every commit, push, session start and turn end. A
    fetched branch must not turn the next session start into a minute of
    silence — and nothing may be skipped: what is not checked stays unverified."""
    _sweep(gated_repo)
    for i in range(4):
        _write(gated_repo, f"docs/note{i}.md", f"{i}\n")
        _git(gated_repo, "add", "-A")
        _git(gated_repo, "commit", "-qm", f"docs: note {i}", "--no-verify")

    result = subprocess.run(
        [sys.executable, str(gated_repo / "scripts" / "process_gate.py"), "sweep"],
        cwd=gated_repo, capture_output=True, text=True, check=False,
        env={**__import__("os").environ, "AGENTSMITH_SWEEP_BATCH": "2"},
    )

    assert "2 more will be swept next time" in result.stdout, result.stdout
    store = json.loads((gated_repo / ".git" / "agentsmith" / "verified").read_text())
    assert sum(1 for c in _git(gated_repo, "rev-list", "HEAD").stdout.split() if c in store["shas"]) == 3


def test_pre_commit_itself_never_refuses_so_the_repair_can_be_committed(gated_repo):
    """The deadlock this design walked into: blocking in pre-commit refuses the
    repair commit as well, because pre-commit runs before the message that says
    what it repairs exists. pre-commit reports; commit-msg decides."""
    _sweep(gated_repo)
    _bypassed_commit(gated_repo)

    hook = subprocess.run(["bash", str(gated_repo / ".githooks" / "pre-commit")],
                          cwd=gated_repo, capture_output=True, text=True, check=False)

    assert hook.returncode == 0, hook.stdout + hook.stderr
    assert "did not pass the gate" in hook.stdout, "it still has to say what is pending"
