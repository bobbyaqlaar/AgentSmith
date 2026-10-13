"""
scripts/test/test_first_commit.py — a scaffolded tenant can make its first commit.

`agentsmith tenant init` prints the exact command to commit its own output, and
that command must pass the tenant's own gate: the design and review trailers,
and the commit guardrails (`commit_guardrails`, on by default in a tenant).
It once did not — the machine-wide pre-commit ran the guardrails over AgentSmith
code vendored into the first commit (.agent-rfc/designs/first-commit-guardrail.md).
Since 3.0.0 nothing is vendored (vendoring-retired.md), and the guardrails are
the gate's: they skip a scaffold file the manifest vouches for, and check it
again the moment the tenant edits it.

The commit here is the one the CLI prints, trailers and all, so the test fails if
the printed instruction stops working for any reason, not only this one.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from test_process_gate import REPO, needs_git

# `install` comes from conftest.py: the same ~/.agent-framework the scratch-tenant
# build uses; the `agentsmith` the tenant's gate asks is this checkout's
# (provider_shim, also from conftest.py).

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
    """A fresh repo scaffolded by the real CLI. Returns the repo and the commit
    command the CLI told the user to run."""
    root = tmp_path / "tenant"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
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


def _printed_args(printed: str) -> list[str]:
    message = re.search(r"git add -A && git commit (.+)$", printed, re.M)
    assert message, f"tenant init no longer prints a commit command:\n{printed}"
    return [a.strip('"') for a in re.findall(r'-m "([^"]+)"', message.group(1))]


def test_the_scaffold_commit_the_cli_prints_is_accepted(install, tmp_path):
    root, printed = _scaffold(install, tmp_path)

    # Nothing of AgentSmith's code is in it (3.0.0): the gate is the provider's.
    assert not (root / "scripts").exists() and not (root / "runtime").exists()
    assert (root / ".agenticframework" / "providers.json").is_file()

    args = _printed_args(printed)
    # The contract, not the count: a subject plus the two trailers the gate
    # resolves (and Refs: RFC-NNN, for the enterprise check).
    assert any(a.startswith("Design: ") for a in args), args
    assert any(a.startswith("Review: ") for a in args), args

    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in args for x in ("-m", a)])

    assert committed.returncode == 0, (
        "the commit `tenant init` prints was refused:\n" + committed.stdout + committed.stderr
    )
    assert _git(root, "log", "--oneline").stdout.strip(), "nothing was committed"


def test_a_tenant_edit_to_a_scaffold_file_is_checked_again(install, tmp_path):
    """The vouch is a hash match, not a path allowlist, and the guardrails are on:
    an AI marker the tenant adds to a file the scaffold wrote fails the commit,
    and says where."""
    root, printed = _scaffold(install, tmp_path)
    edited = root / "docs" / "PRODUCT_BACKLOG.md"
    edited.write_text(edited.read_text() + "\n# TODO: " + "agent finish this\n")

    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in _printed_args(printed) for x in ("-m", a)])

    out = committed.stdout + committed.stderr
    assert committed.returncode == 1, f"an edited scaffold file must lose its vouch:\n{out}"
    assert "docs/PRODUCT_BACKLOG.md" in out and "AI marker" in out, out


def test_the_scaffold_passes_the_enterprise_guardrails(install, tmp_path):
    """With an org policy on the machine the gate also wants an RFC at
    .agent-rfc/ depth 1 and an RFC-NNN in the message — the scaffold writes the
    one and prints the other (first-commit-guardrail.md, Pass 4)."""
    (install / ".agent-framework" / "agenticframework-org.yaml").write_text("org: test\n")
    root, printed = _scaffold(install, tmp_path)

    depth1 = list((root / ".agent-rfc").glob("*.md"))
    assert depth1, "no RFC at .agent-rfc/ depth 1 — the enterprise check counts only these"

    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in _printed_args(printed) for x in ("-m", a)])

    out = committed.stdout + committed.stderr
    assert committed.returncode == 0, f"the enterprise first commit is refused:\n{out}"
