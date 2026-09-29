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
    # The contract, not the count: a subject plus the two trailers the gate
    # resolves. A third trailer was added later (Refs: RFC-NNN, for the
    # enterprise commit-msg rule), and pinning the count made that a failure.
    assert len(args) >= 3, args
    assert any(a.startswith("Design: ") for a in args), args
    assert any(a.startswith("Review: ") for a in args), args

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


def _ship_defects(home: Path) -> None:
    """Put both guardrail defects into the framework the fixture will vendor, so
    the tenant receives them in `scripts/` and the manifest records them — a
    released version that shipped code its own guardrails reject. Done before
    `tenant init` so nothing is hand-edited afterwards: the tenant's files and its
    manifest both come from AgentSmith, which is the situation the vouch is for."""
    fw = home / ".agent-framework" / "scripts"
    bad = fw / "gate_history.py"
    bad.write_text(bad.read_text() + "\n\ndef _shipped():\n    try:\n        pass\n    except OSError:\n        pass\n")
    marked = fw / "map_codebase.py"
    marked.write_text(marked.read_text() + "\n# TODO: " + "agent revisit this\n")


def test_a_defect_shipped_in_vendored_code_does_not_block_the_first_commit(install, tmp_path):
    """Part B. The tenant did not write scripts/gate_history.py and cannot fix it,
    so an empty handler or a stray marker in it must not refuse their first
    commit. Both are skipped because the manifest vouches for the file AND it
    still hashes to what was recorded."""
    _ship_defects(install)
    root, printed = _scaffold(install, tmp_path)
    args = [a.strip('"') for a in re.findall(r'-m "([^"]+)"', printed.split("git add -A")[-1])]

    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in args for x in ("-m", a)])

    out = committed.stdout + committed.stderr
    assert committed.returncode == 0, out
    assert "are AgentSmith's own" in out, f"the skip has to say it happened:\n{out}"
    assert "guardrails passed" in out.lower(), out


def test_a_tenant_edit_to_a_vendored_file_is_checked_again(install, tmp_path):
    """The other half of the vouch, and the one that makes it safe: the skip is a
    hash match, not a path allowlist. Edit a vendored file and it is checked like
    anything else — so this must FAIL, on a marker the tenant introduced."""
    root, printed = _scaffold(install, tmp_path)
    edited = root / "scripts" / "map_codebase.py"
    edited.write_text(edited.read_text() + "\n# TODO: " + "agent finish this\n")
    args = [a.strip('"') for a in re.findall(r'-m "([^"]+)"', printed.split("git add -A")[-1])]

    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in args for x in ("-m", a)])

    out = committed.stdout + committed.stderr
    assert committed.returncode == 1, f"an edited vendored file must lose its vouch:\n{out}"
    assert "Unresolved AI marker" in out, out
    assert "map_codebase.py" in out, out


def test_the_scaffold_writes_an_rfc_the_enterprise_guardrail_accepts(install, tmp_path):
    """Part A. Guardrail 4 counts *.md at .agent-rfc/ DEPTH 1 wherever an org
    policy exists; the scaffold design sits at depth 2, so this commit used to be
    refused on an enterprise machine (first-commit-guardrail.md, Pass 4)."""
    (install / ".agent-framework" / "agenticframework-org.yaml").write_text("org: test\n")
    root, printed = _scaffold(install, tmp_path)

    depth1 = list((root / ".agent-rfc").glob("*.md"))
    assert depth1, "no RFC at .agent-rfc/ depth 1 — Guardrail 4 counts only these"
    assert not any(line.startswith(("\u26a0\ufe0f", "\u274c")) for line in depth1[0].read_text().splitlines()), (
        "a column-0 warning in a scaffolded file fails .github/scratch-tenants/build.sh"
    )

    args = [a.strip('"') for a in re.findall(r'-m "([^"]+)"', printed.split("git add -A")[-1])]
    _git(root, "add", "-A")
    committed = _git(root, "commit", *[x for a in args for x in ("-m", a)])

    out = committed.stdout + committed.stderr
    assert committed.returncode == 0, f"the enterprise first commit is still refused:\n{out}"
    assert "requires at least one RFC" not in out, out
