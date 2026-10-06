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


# ── A mutation is caught by its first failing test (mutation-first-failure.md) ──


def _toy_suite(tmp_path: Path, mutation: "mc.Mutation") -> "mc.Suite":
    """A target module and three tests, each of which records that it ran. Only
    the FIRST depends on the target's value, so a mutation of it is caught there."""
    (tmp_path / "target.py").write_text("VALUE = 1  # the value under test\n")
    ran = tmp_path / "ran.log"
    header = ("import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent))\n"
              f"LOG = pathlib.Path({str(ran)!r})\n")
    (tmp_path / "test_toy.py").write_text(
        header
        + "def test_the_value():\n    LOG.open('a').write('value\\n')\n    import target\n"
          "    assert target.VALUE == 1\n"
        + "".join(f"def test_other_{i}():\n    LOG.open('a').write('other\\n')\n" for i in range(3)))
    return mc.Suite(name="toy", tests=(str(tmp_path / "test_toy.py"),), mutations=(mutation,))


def _ran(tmp_path: Path) -> list[str]:
    log = tmp_path / "ran.log"
    return log.read_text().split() if log.exists() else []


def test_a_caught_mutation_stops_at_its_first_failing_test(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "REPO", tmp_path)
    suite = _toy_suite(tmp_path, mc.Mutation("the value moves", "target.py", "VALUE = 1", "VALUE = 2"))

    problems = mc.run_suite(suite)

    assert problems == []
    # The baseline ran all four; the mutation run stopped at the first, which failed.
    assert _ran(tmp_path) == ["value", "other", "other", "other", "value"]
    assert (tmp_path / "target.py").read_text() == "VALUE = 1  # the value under test\n", "restored"


def test_a_surviving_mutation_still_runs_every_test(tmp_path, monkeypatch):
    """Stopping early must never hide a survivor: nothing fails, so nothing stops."""
    monkeypatch.setattr(mc, "REPO", tmp_path)
    suite = _toy_suite(tmp_path, mc.Mutation("only the comment moves", "target.py", "# the value", "# a value"))

    problems = mc.run_suite(suite)

    assert len(problems) == 1 and "SURVIVED" in problems[0]
    assert _ran(tmp_path) == ["value", "other", "other", "other"] * 2


def test_a_baseline_runs_every_test_even_after_a_failure(tmp_path, monkeypatch):
    """A baseline that stopped at its first failure would hide the second."""
    calls = []
    monkeypatch.setattr(mc.subprocess, "run", lambda args, **kw: calls.append(args) or
                        subprocess.CompletedProcess(args, 1, "", "1 failed"))
    suite = mc.Suite(name="toy", tests=("t.py",),
                     mutations=(mc.Mutation("m", "scripts/mutation_check.py", "def main", "def main"),))

    problems = mc.run_suite(suite)

    assert "BASELINE ALREADY FAILING" in problems[0]
    assert "-x" not in calls[0]
