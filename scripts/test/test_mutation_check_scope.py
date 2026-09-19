"""
scripts/test/test_mutation_check_scope.py — a slow mutation suite runs when what
it protects changes (.agent-rfc/designs/mutation-ci-scope.md).

`--changed-since REF` skips a suite that declares `watch` when none of the files
it watches changed; a suite without `watch` always runs; and a base the clone
cannot use runs everything. The selection is read from real git history.
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import mutation_check as mc

ZEROS = "0" * 40


def _suite(name: str, watch: tuple[str, ...] = ()) -> "mc.Suite":
    return mc.Suite(name=name, tests=("t.py",), mutations=(), watch=watch)


def test_a_suite_without_watch_always_runs():
    run, skipped = mc.select_suites((_suite("always"),), changed=set())
    assert [s.name for s in run] == ["always"] and skipped == []


def test_a_watched_suite_is_skipped_when_nothing_it_watches_changed():
    run, skipped = mc.select_suites((_suite("slow", ("hooks/**",)),), changed={"docs/UserManual.md"})
    assert run == []
    assert [s.name for s, _ in skipped] == ["slow"]
    assert "none of the files it watches changed" in skipped[0][1]


def test_a_watched_suite_runs_when_a_watched_file_changed():
    run, _ = mc.select_suites((_suite("slow", ("hooks/**", "runtime/adopt.py")),),
                              changed={"README.md", "hooks/post-checkout"})
    assert [s.name for s in run] == ["slow"]


def test_unknown_changes_run_everything():
    run, skipped = mc.select_suites((_suite("slow", ("hooks/**",)), _suite("always")), changed=None)
    assert [s.name for s in run] == ["slow", "always"] and skipped == []


@pytest.fixture()
def history(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    git("init", "-q", "-b", "main")
    (root / "a.txt").write_text("1")
    git("add", "-A")
    git("commit", "-q", "-m", "one")
    base = git("rev-parse", "HEAD")
    (root / "hooks").mkdir()
    (root / "hooks" / "post-checkout").write_text("x")
    git("add", "-A")
    git("commit", "-q", "-m", "two")
    return root, base


def test_the_changed_files_come_from_git(history):
    root, base = history
    assert mc.changed_files(base, cwd=root) == {"hooks/post-checkout"}
    assert mc.changed_files("HEAD", cwd=root) == set()


def test_uncommitted_and_new_files_count_as_changed(history):
    """Locally, the edit in progress is the change: skipping the suite that
    guards a file being edited because it is not committed yet would skip it
    exactly when it matters. In CI the tree is clean, so this adds nothing."""
    root, _ = history
    (root / "a.txt").write_text("edited")
    (root / "new.py").write_text("x = 1")
    assert mc.changed_files("HEAD", cwd=root) == {"a.txt", "new.py"}


@pytest.mark.parametrize("ref", ["", ZEROS, "1234567890abcdef1234567890abcdef12345678"])
def test_a_base_the_clone_cannot_use_means_unknown(history, ref):
    """A new branch (all zeros), no base at all, or a commit a force-push or a
    shallow checkout left out: the changes are unknown, not empty."""
    root, _ = history
    assert mc.changed_files(ref, cwd=root) is None


def test_the_tenant_adopt_suite_watches_everything_it_mutates_and_tests():
    """`watch` is a hand-kept list; this keeps it from drifting behind the
    suite's own mutations and tests, which would skip it for a change that
    breaks it."""
    [suite] = [s for s in mc.CATALOGUE if s.name == "tenant_adopt"]
    for path in {m.path for m in suite.mutations} | set(suite.tests) | {"scripts/mutation_check.py"}:
        assert any(fnmatch.fnmatchcase(path, glob) for glob in suite.watch), f"{path} is not watched"


def test_only_the_slow_suite_is_narrowed():
    assert [s.name for s in mc.CATALOGUE if s.watch] == ["tenant_adopt"]


def test_the_cli_names_a_skipped_suite_and_does_not_count_it_as_caught(tmp_path):
    """Run from its own committed copy, so the answer does not depend on what
    this checkout has uncommitted — the harness is one of the watched files."""
    root = tmp_path / "harness"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "mutation_check.py").write_text((REPO / "scripts" / "mutation_check.py").read_text())
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "harness"]):
        subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args], check=True)

    result = subprocess.run([sys.executable, str(root / "scripts" / "mutation_check.py"), "--changed-since", "HEAD",
                             "tenant_adopt"], cwd=root, capture_output=True, text=True, check=False, timeout=120)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "tenant_adopt" in result.stdout and "skipped" in result.stdout
    assert "all caught" not in result.stdout, "a suite that did not run is not a suite that caught everything"


def test_the_cli_says_why_it_ran_everything(tmp_path):
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "mutation_check.py"), "--changed-since", ZEROS,
                             "--list"], cwd=REPO, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0
    assert "cannot tell what changed" in result.stdout
