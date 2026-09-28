"""
scripts/test/test_first_commit.py — a scaffolded tenant can make its first commit.

`agentsmith tenant init` prints the exact command to commit its own output. That
command was refused: `hooks/pre-commit` runs `scripts/check_bare_except.py` over
every STAGED `.py` file, a first commit stages the vendored `scripts/` and
`runtime/`, and thirteen unmarked empty handlers in AgentSmith's own code failed it
(.agent-rfc/designs/first-commit-guardrail.md).

Nothing covered this. AgentSmith's own commits never stage those files together,
and the scratch tenants in .github/scratch-tenants/ all have history —
`build.sh` copies into an existing repository, so only changed files stage. Only
`git init` stages the whole framework at once, which is what onboarding does.

The commit here is the one the CLI prints, trailers and all, so the test fails if
the printed instruction stops working for any reason, not only this one.

Covers a DEFAULT machine only. Where an org policy file exists, Guardrail 4 wants
an RFC at `.agent-rfc/` depth 1 and the scaffold writes one at depth 2, so the
same commit is still refused \u2014 verified, unfixed, and recorded in
docs/PRODUCT_BACKLOG.md, because both candidate fixes change what an RFC means.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from test_process_gate import REPO, needs_git

# `install` comes from conftest.py: the same ~/.agent-framework the scratch-tenant
# build uses, rather than a second copy of it. The defect only appears when the
# framework is really vendored, and that fixture is what makes vendoring happen
# offline.

pytestmark = needs_git


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
        capture_output=True,
        text=True,
        check=False,
        # The fixture's ~/.agent-framework has no .venv, so the gate's interpreter
        # search would find nothing and exit 3. Naming this interpreter is what the
        # gate's own error message tells a real user to do; it does not weaken the
        # test, which is about which FILES the hook checks, not how it starts.
        env={**os.environ, "AGENTSMITH_PYTHON": sys.executable},
    )


def _scaffold(home: Path, tmp_path: Path) -> tuple[Path, str]:
    """A fresh repo scaffolded by the real CLI, with the framework vendored from
    the `install` fixture's ~/.agent-framework. Returns the repo and the commit
    command the CLI told the user to run."""
    root = tmp_path / "tenant"
    root.mkdir()
    # WITH the machine's git template, unlike most tests here: `git init` is how a
    # real repository gets AgentSmith's post-checkout, and post-checkout is what
    # vendors scripts/ and runtime/. Passing `--template=` (empty) produces a
    # scaffold the CLI itself calls "not done yet", and then there are no vendored
    # .py files to stage — which is the entire mechanism under test.
    subprocess.run(
        ["git", "init", "-q", "-b", "main", f"--template={home / '.git_templates'}", str(root)],
        check=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "runtime.cli",
            "tenant",
            "init",
            "demo-app",
            "--stack",
            "python-fastapi",
            "--root",
            str(root),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "AGENTSMITH_DIR": str(REPO)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return root, result.stdout


def test_the_scaffold_commit_the_cli_prints_is_accepted(install, tmp_path):
    root, printed = _scaffold(install, tmp_path)

    # The framework must actually be vendored, or this test proves nothing: the
    # defect only appears because these .py files are staged.
    vendored = list((root / "scripts").glob("*.py"))
    assert len(vendored) > 20, f"only {len(vendored)} vendored scripts — nothing to trip the guardrail"

    # No remote, so hooks/post-commit's auto-tag-and-push cannot reach anything.
    assert _git(root, "remote").stdout.strip() == ""

    message = re.search(r"git add -A && git commit (.+)$", printed, re.M)
    assert message, f"tenant init no longer prints a commit command:\n{printed}"
    args = [a.strip('"') for a in re.findall(r'-m "([^"]+)"', message.group(1))]
    assert len(args) == 3, args

    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in args for x in ("-m", a)])

    assert committed.returncode == 0, (
        "the commit `tenant init` prints was refused:\n" + committed.stdout + committed.stderr
    )
    assert _git(root, "log", "--oneline").stdout.strip(), "nothing was committed"


def test_the_pre_commit_guardrail_still_runs_on_that_commit(install, tmp_path):
    """Guards the test above: it would also pass if the guardrail had been
    switched off or skipped rather than satisfied."""
    root, printed = _scaffold(install, tmp_path)
    args = [a.strip('"') for a in re.findall(r'-m "([^"]+)"', printed.split("git add -A")[-1])]
    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in args for x in ("-m", a)])

    assert committed.returncode == 0, committed.stdout + committed.stderr
    out = committed.stdout + committed.stderr
    assert "pre-commit guardrail" in out.lower(), f"the guardrail did not run:\n{out}"
    assert "guardrails passed" in out.lower(), f"the guardrail ran but did not pass:\n{out}"
