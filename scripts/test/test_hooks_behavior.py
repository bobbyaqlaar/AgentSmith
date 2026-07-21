"""
scripts/test/test_hooks_behavior.py — behavioral tests for the pre-commit and
commit-msg hooks (TestCoverageReview-2026-07-21 gap 7). Until now only
`bash -n` syntax and the opt-in *logic* via verify_system --check-hooks were
checked — no test actually committed against the hooks.

Each test runs real `git commit` in a scratch repo with the hooks installed
in .git/hooks and HOME pointed at a tmp dir (the opt-in gate and enterprise
mode both key off $HOME/.agent-framework/agenticframework-org.yaml, so the
host machine's real state must never leak in).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
CHECKER = Path(__file__).resolve().parents[1] / "check_bare_except.py"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)

    work = tmp_path / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    hooks = work / ".git" / "hooks"
    for name in ("pre-commit", "commit-msg"):
        dst = hooks / name
        shutil.copy(HOOKS_DIR / name, dst)
        dst.chmod(0o755)
    return work


def _commit(repo: Path, filename: str, content: str, message: str) -> subprocess.CompletedProcess:
    (repo / filename).parent.mkdir(parents=True, exist_ok=True)
    (repo / filename).write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    return subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.email=test@example.com", "-c", "user.name=Test",
            "commit", "-q", "-m", message,
        ],
        capture_output=True,
        text=True,
    )


def _opt_in(repo: Path) -> None:
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "enabled").touch()


# ── Opt-in gate ──────────────────────────────────────────────────────────────


def test_unopted_repo_is_left_alone(repo):
    """Cloning an unrelated repo must never be policed (README opt-in model):
    both a non-conventional message and an AI marker sail through."""
    r = _commit(repo, "notes.txt", "TODO: agent fix this later\n", "whatever message")
    assert r.returncode == 0, r.stderr


def test_disable_ai_stack_bypasses_even_when_opted_in(repo, monkeypatch):
    _opt_in(repo)
    monkeypatch.setenv("DISABLE_AI_STACK", "true")
    r = _commit(repo, "notes.txt", "TODO: agent later\n", "bad message")
    assert r.returncode == 0, r.stderr


# ── commit-msg: Conventional Commits ─────────────────────────────────────────


def test_commit_msg_rejects_non_conventional(repo):
    _opt_in(repo)
    r = _commit(repo, "a.txt", "clean\n", "updated some stuff")
    assert r.returncode != 0
    assert "Conventional Commits" in r.stdout + r.stderr


def test_commit_msg_accepts_conventional_variants(repo):
    _opt_in(repo)
    for i, msg in enumerate(
        ["feat(agents): add prediction pipeline", "docs: update guide", "fix!: breaking hotfix"]
    ):
        r = _commit(repo, f"f{i}.txt", "clean\n", msg)
        assert r.returncode == 0, f"{msg!r} rejected: {r.stdout}{r.stderr}"


def test_commit_msg_rejects_overlong_summary(repo):
    _opt_in(repo)
    r = _commit(repo, "a.txt", "clean\n", "feat: " + "x" * 80)
    assert r.returncode != 0


# ── pre-commit guardrails ────────────────────────────────────────────────────


def test_pre_commit_blocks_ai_markers(repo):
    _opt_in(repo)
    r = _commit(repo, "code.py", "# TODO: agent finish this\n", "feat: marker")
    assert r.returncode != 0
    assert "Unresolved AI marker" in r.stdout + r.stderr


def test_pre_commit_blocks_empty_js_catch(repo):
    _opt_in(repo)
    r = _commit(repo, "app.js", "try { f(); } catch (e) {}\n", "feat: js")
    assert r.returncode != 0
    assert "Empty catch block" in r.stdout + r.stderr


def test_pre_commit_blocks_go_double_blank(repo):
    _opt_in(repo)
    r = _commit(repo, "main.go", "_, _ = doThing()\n", "feat: go")
    assert r.returncode != 0
    assert "Double blank identifier" in r.stdout + r.stderr


def test_pre_commit_blocks_empty_python_except_via_vendored_checker(repo, tmp_path):
    """The hook prefers the GLOBAL ~/.agent-framework/scripts copy (the
    FIXES 'global-copy drift' lesson) — vendor it into the fake HOME."""
    _opt_in(repo)
    vendored = Path(tmp_path / "home") / ".agent-framework" / "scripts"
    vendored.mkdir(parents=True)
    shutil.copy(CHECKER, vendored / "check_bare_except.py")
    r = _commit(
        repo, "svc.py", "try:\n    f()\nexcept Exception:\n    pass\n", "feat: py"
    )
    assert r.returncode != 0
    assert "empty except handler" in r.stdout + r.stderr
    # The documented suppression form is accepted
    r2 = _commit(
        repo,
        "svc.py",
        "try:\n    f()\nexcept Exception:  # fail-open: telemetry only\n    pass\n",
        "feat: py suppressed",
    )
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_pre_commit_passes_clean_change(repo):
    _opt_in(repo)
    r = _commit(repo, "clean.py", "def ok():\n    return 1\n", "feat: clean change")
    assert r.returncode == 0, r.stdout + r.stderr


# ── Enterprise mode (org policy present in $HOME) ────────────────────────────


def _enable_enterprise(tmp_path) -> None:
    org = Path(tmp_path / "home") / ".agent-framework"
    org.mkdir(parents=True, exist_ok=True)
    (org / "agenticframework-org.yaml").write_text("org: test\n")


def test_enterprise_requires_rfc_reference_in_message(repo, tmp_path):
    _enable_enterprise(tmp_path)
    (repo / ".agent-rfc").mkdir()
    (repo / ".agent-rfc" / "001-init.md").write_text("# RFC 001\n")
    r = _commit(repo, "a.txt", "clean\n", "feat: no rfc reference")
    assert r.returncode != 0
    assert "RFC-NNN" in r.stdout + r.stderr
    r2 = _commit(repo, "a.txt", "clean2\n", "feat: with reference (RFC-001)")
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_enterprise_requires_an_open_rfc_to_exist(repo, tmp_path):
    _enable_enterprise(tmp_path)  # no .agent-rfc/ in repo
    r = _commit(repo, "a.txt", "clean\n", "feat: something (RFC-001)")
    assert r.returncode != 0
    assert "at least one RFC" in r.stdout + r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
