"""
scripts/test/test_hook_chain.py — the hooks a repository already ran keep
running once AgentSmith arms `.githooks` (.agent-rfc/designs/tenant-adopt.md).

`core.hooksPath` names one directory, so arming `.githooks` used to switch off
whatever ran before — husky, pre-commit, or the machine's own post-checkout,
which is why `tenant init` repositories were never vendored. `.githooks/chain`
runs the same-named hook from `agentsmith.chainHooksPath`, after the gate.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_process_gate import REPO, needs_git

pytestmark = needs_git

HOOKS = ("process-gate", "commit-msg", "pre-commit", "pre-push", "chain")


def _git(root: Path, *args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                          capture_output=True, text=True, check=False, **kw)


def _hook(directory: Path, name: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(0o755)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A repository with AgentSmith's `.githooks` armed and no gate config — the
    gate itself passes everything, so only the chain is under test."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    (root / ".githooks").mkdir()
    for name in HOOKS:
        shutil.copy(REPO / ".githooks" / name, root / ".githooks" / name)
    _git(root, "config", "core.hooksPath", ".githooks")
    return root


@pytest.fixture()
def prior(repo):
    """The hooks the repository ran before: each leaves a mark."""
    directory = repo / ".hooks"
    marks = repo.parent / "marks"
    marks.mkdir()
    _hook(directory, "pre-commit", f'echo pre-commit >> "{marks}/ran"')
    _hook(directory, "commit-msg", f'echo "commit-msg $(head -n1 "$1")" >> "{marks}/ran"')
    _hook(directory, "pre-push", f'cat >> "{marks}/pushed"; echo pre-push >> "{marks}/ran"')
    _hook(directory, "post-checkout", f'echo "post-checkout $3" >> "{marks}/ran"')
    return directory


def _ran(repo: Path) -> str:
    marks = repo.parent / "marks" / "ran"
    return marks.read_text() if marks.exists() else ""


def _commit(repo: Path, subject: str = "chore: one") -> subprocess.CompletedProcess:
    (repo / "f.txt").write_text(subject)
    _git(repo, "add", "f.txt")
    return _git(repo, "commit", "-m", subject)


def test_without_the_setting_nothing_is_chained(repo, prior):
    """AgentSmith itself sets nothing: its hooks behave exactly as before."""
    assert _commit(repo).returncode == 0
    assert _ran(repo) == ""


def test_the_prior_hooks_run_after_the_gate(repo, prior):
    _git(repo, "config", "agentsmith.chainHooksPath", ".hooks")

    result = _commit(repo, "chore: chained")

    assert result.returncode == 0, result.stderr
    assert _ran(repo).splitlines() == ["pre-commit", "commit-msg chore: chained"]


def test_a_failing_prior_hook_still_blocks_the_commit(repo, prior):
    _hook(prior, "pre-commit", "echo 'lint failed' >&2; exit 1")
    _git(repo, "config", "agentsmith.chainHooksPath", ".hooks")

    result = _commit(repo)

    assert result.returncode != 0 and "lint failed" in result.stderr


def test_a_commit_the_gate_refuses_never_reaches_the_prior_hook(repo, prior):
    _git(repo, "config", "agentsmith.chainHooksPath", ".hooks")

    result = _commit(repo, "not a conventional subject")

    assert result.returncode != 0
    assert "commit-msg" not in _ran(repo), "the prior hook runs after the gate passes, never instead of it"


def test_a_message_the_process_gate_refuses_never_reaches_the_prior_commit_msg(repo, prior, tmp_path, monkeypatch):
    """A well-formed subject, refused by the gate itself (here: an interpreter
    that fails `commit-msg` only, so the sweep in pre-commit still passes)."""
    fake = tmp_path / "python"
    fake.write_text(f'#!/usr/bin/env bash\n[ "$2" = commit-msg ] && exit 1\nexec "{sys.executable}" "$@"\n')
    fake.chmod(0o755)
    monkeypatch.setenv("AGENTSMITH_PYTHON", str(fake))
    _git(repo, "config", "agentsmith.chainHooksPath", ".hooks")

    result = _commit(repo, "chore: refused by the gate")

    assert result.returncode != 0
    assert _ran(repo).splitlines() == ["pre-commit"], "the prior commit-msg runs only after the gate passes"


def test_the_prior_pre_push_gets_the_refs_on_stdin(repo, prior, tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(repo, "config", "agentsmith.chainHooksPath", ".hooks")
    assert _commit(repo).returncode == 0

    result = _git(repo, "push", "-q", str(remote), "main")

    assert result.returncode == 0, result.stderr
    assert "refs/heads/main" in (tmp_path / "marks" / "pushed").read_text()


def test_a_chain_that_points_at_itself_does_not_loop(repo, prior):
    _git(repo, "config", "agentsmith.chainHooksPath", ".githooks")

    result = subprocess.run(["bash", str(repo / ".githooks" / "chain"), "pre-commit"], cwd=repo,
                            capture_output=True, text=True, check=False, timeout=30)

    assert result.returncode == 0


def _chain(repo: Path, prior: Path) -> list[str]:
    sys.path.insert(0, str(REPO))
    from runtime.adopt import chain_hooks

    return chain_hooks(repo, prior)


def test_chaining_writes_a_stub_for_each_hook_the_gate_does_not_own(repo, prior):
    written = _chain(repo, prior)

    assert written == [".githooks/post-checkout"]
    assert _git(repo, "config", "--get", "agentsmith.chainHooksPath").stdout.strip() == str(prior)
    assert _commit(repo).returncode == 0
    _git(repo, "checkout", "-q", "-b", "other")
    assert "post-checkout 1" in _ran(repo), "the stub runs the prior post-checkout on a branch checkout"


def test_chaining_a_post_commit_turns_autopush_off_unless_it_was_set(repo, prior):
    _hook(prior, "post-commit", "true")

    _chain(repo, prior)

    assert _git(repo, "config", "--get", "agentsmith.autopush").stdout.strip() == "false"


def test_an_explicit_autopush_is_left_alone(repo, prior):
    _hook(prior, "post-commit", "true")
    _git(repo, "config", "agentsmith.autopush", "true")

    _chain(repo, prior)

    assert _git(repo, "config", "--get", "agentsmith.autopush").stdout.strip() == "true"


def test_the_prior_directory_is_found(repo, prior):
    sys.path.insert(0, str(REPO))
    from runtime.adopt import prior_hooks_dir

    assert prior_hooks_dir(repo) is None, "armed at .githooks, with only samples in .git/hooks"
    _git(repo, "config", "core.hooksPath", ".nowhere")
    assert prior_hooks_dir(repo) is None, "a hooks path that does not exist ran nothing"
    _git(repo, "config", "core.hooksPath", ".hooks")
    assert prior_hooks_dir(repo) == prior
    _git(repo, "config", "--unset", "core.hooksPath")
    _hook(repo / ".git" / "hooks", "pre-commit", "true")
    (repo / ".git" / "hooks" / "pre-push.sample").write_text("#!/bin/sh\n")
    assert prior_hooks_dir(repo) == repo / ".git" / "hooks"
