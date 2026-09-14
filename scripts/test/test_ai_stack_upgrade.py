"""
scripts/test/test_ai_stack_upgrade.py — `agentsmith upgrade` (formerly the
`ai-stack-upgrade` shell function) commits what it vendors, including files the
tenant has never had.

Its "anything to commit?" check was `git diff --quiet`, which ignores untracked
files. A first-time vendor — runtime/ on a tenant onboarded before runtime/ was
vendored, or a newly shipped base fixture — copied the files, printed
"No changes", and committed nothing.

The function lived in the shell profile, so these tests used to carve it out of
install-ai-stack.sh and run it under bash and zsh. It is Python now
(runtime/machine/upgrade.py); they run the real command, `agentsmith upgrade`,
against a fake HOME.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


def _run_upgrade(repo: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    # The command commits, and HOME is a fake with no ~/.gitconfig. macOS git
    # then auto-detects an identity from the hostname; a Linux CI runner cannot,
    # so the commit failed there and only there.
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO),
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.com",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.com",
    }
    return subprocess.run(
        # -P: the installed `agentsmith` script does not put the working
        # directory on sys.path, and a tenant's own `runtime/` there would shadow ours.
        [sys.executable, "-P", "-m", "runtime.cli", "upgrade", "--to", "9.9.9"],
        cwd=repo, env=env, capture_output=True, text=True, check=False,
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        check=True, capture_output=True, text=True,
    ).stdout


@pytest.mark.parametrize("current_version", ["1.0.0", "9.9.9"])
def test_first_time_vendored_files_are_committed(tmp_path, monkeypatch, current_version):
    """9.9.9 = already on the target version, so tenant.yaml is unchanged and
    the ONLY changes are untracked files — the case `git diff --quiet` missed."""
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    (fw / "scripts").mkdir(parents=True)
    (fw / "scripts" / "run-evals.py").write_text("# run-evals\n")
    (fw / "runtime").mkdir()
    (fw / "runtime" / "judging.py").write_text("# judging\n")
    (fw / "runtime" / "llm_gateway.py").write_text("# llm_gateway\n")
    (fw / "fixtures" / "security").mkdir(parents=True)
    (fw / "fixtures" / "security" / "control_registry.json").write_text("[]\n")
    (fw / "fixtures" / "rag_poison_base.json").write_text("[]\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DISABLE_AI_STACK", "true")

    repo = tmp_path / "tenant"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "tenant.yaml").write_text(
        f'tenant:\n  id: t\nframework:\n  version: "{current_version}"\n'
    )
    (repo / "scripts").mkdir()
    (repo / "scripts" / "run-evals.py").write_text("# run-evals\n")  # already current
    (repo / "fixtures").mkdir()
    (repo / "fixtures" / "applicants.json").write_text("[]\n")  # tenant-owned
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    result = _run_upgrade(repo, tmp_path)

    assert "No changes" not in result.stdout, result.stdout
    tracked = set(_git(repo, "ls-files").split())
    assert "runtime/judging.py" in tracked, result.stdout + result.stderr
    assert "fixtures/security/control_registry.json" in tracked
    assert "fixtures/rag_poison_base.json" in tracked
    assert _git(repo, "status", "--porcelain") == ""
    # The lint-isolation config is regenerated to cover what was vendored.
    assert '"judging.py"' in (repo / "runtime" / "ruff.toml").read_text()
    assert '"run-evals.py"' in (repo / "scripts" / "ruff.toml").read_text()


def test_upgrade_spares_a_tenants_own_scripts_test_and_runtime_package(tmp_path, monkeypatch):
    """The upgrade pruned scripts/test AFTER copying into the tenant's scripts/,
    deleting the tenant's own tests; and it merged into, then `git add`-ed, any
    runtime/ — including a tenant's own package of that name."""
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    (fw / "scripts" / "test").mkdir(parents=True)
    (fw / "scripts" / "run-evals.py").write_text("# run-evals\n")
    (fw / "scripts" / "test" / "test_framework.py").write_text("# framework's own\n")
    (fw / "runtime").mkdir()
    (fw / "runtime" / "llm_gateway.py").write_text("# llm_gateway\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DISABLE_AI_STACK", "true")

    repo = tmp_path / "tenant"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "tenant.yaml").write_text('tenant:\n  id: t\nframework:\n  version: "1.0.0"\n')
    (repo / "scripts" / "test").mkdir(parents=True)
    (repo / "scripts" / "test" / "test_release.py").write_text("# tenant's own test\n")
    (repo / "runtime").mkdir()
    (repo / "runtime" / "__init__.py").write_text("# tenant's own package\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    (repo / "runtime" / "wip.py").write_text("# uncommitted tenant work\n")

    result = _run_upgrade(repo, tmp_path)

    assert (repo / "scripts" / "test" / "test_release.py").exists(), result.stdout
    assert not (repo / "scripts" / "test" / "test_framework.py").exists()
    assert not (repo / "runtime" / "llm_gateway.py").exists()
    assert "not AgentSmith's" in result.stdout
    assert "runtime/wip.py" not in _git(repo, "ls-files"), "a tenant's own runtime/ was swept into the commit"


def test_upgrade_without_base_fixtures_installed_still_completes(tmp_path, monkeypatch):
    """An install that predates base-fixture vendoring has none. Under zsh a
    glob over them aborted the shell function before it committed anything."""
    fw = tmp_path / "home" / ".agent-framework"
    (fw / "scripts").mkdir(parents=True)
    (fw / "scripts" / "run-evals.py").write_text("# run-evals\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DISABLE_AI_STACK", "true")

    repo = tmp_path / "tenant"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "tenant.yaml").write_text('tenant:\n  id: t\nframework:\n  version: "1.0.0"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    result = _run_upgrade(repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scripts/run-evals.py" in _git(repo, "ls-files"), result.stdout + result.stderr


def test_upgrade_prunes_framework_internal_runtime_tests(tmp_path, monkeypatch):
    """Tenants vendored before the allowlist carry all of runtime/test/. The
    upgrade must leave only the harness's suites, or the tenant's pytest keeps
    failing on the framework's own tests."""
    fw = tmp_path / "home" / ".agent-framework"
    (fw / "scripts").mkdir(parents=True)
    (fw / "scripts" / "run-evals.py").write_text("# run-evals\n")
    (fw / "runtime" / "test").mkdir(parents=True)
    (fw / "runtime" / "llm_gateway.py").write_text("# llm_gateway\n")
    (fw / "runtime" / "test" / "test_hitl_gate.py").write_text("# kept\n")
    (fw / "runtime" / "test" / "test_framework_version.py").write_text("# framework-internal\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DISABLE_AI_STACK", "true")

    repo = tmp_path / "tenant"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "tenant.yaml").write_text('tenant:\n  id: t\nframework:\n  version: "1.0.0"\n')
    (repo / "runtime" / "test").mkdir(parents=True)
    (repo / "runtime" / "llm_gateway.py").write_text("# llm_gateway\n")
    (repo / "runtime" / "test" / "test_framework_version.py").write_text("# vendored whole, earlier\n")
    (repo / "runtime" / "test" / "test_pg_pool.py").write_text("# vendored whole, earlier\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    result = _run_upgrade(repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (repo / "runtime" / "test").iterdir()) == ["test_hitl_gate.py"]
    tracked = _git(repo, "ls-files")
    assert "runtime/test/test_pg_pool.py" not in tracked
    assert "runtime/test/test_hitl_gate.py" in tracked


@pytest.mark.parametrize("has_requirements", [True, False])
def test_upgrade_refuses_to_vendor_into_a_package_consumer(tmp_path, monkeypatch, has_requirements):
    """KYC Sentinel pins agentsmith-runtime; vendored runtime/ at its root would
    shadow the pin. `has_requirements=False` (pyproject only) was the zsh case:
    a `requirements*.txt` glob with no match aborted the shell function."""
    fw = tmp_path / "home" / ".agent-framework"
    (fw / "scripts").mkdir(parents=True)
    (fw / "scripts" / "run-evals.py").write_text("# run-evals\n")
    (fw / "runtime").mkdir()
    (fw / "runtime" / "llm_gateway.py").write_text("# llm_gateway\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DISABLE_AI_STACK", "true")

    repo = tmp_path / "tenant"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "tenant.yaml").write_text('tenant:\n  id: t\nframework:\n  version: "1.0.0"\n')
    dep = "agentsmith-runtime @ git+https://github.com/bobbyaqlaar/AgentSmith@v1.3.0"
    if has_requirements:
        (repo / "requirements.txt").write_text(dep + "\n")
    else:
        (repo / "pyproject.toml").write_text(f'[project]\nname = "t"\ndependencies = [\n  "{dep}",\n]\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    result = _run_upgrade(repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "depends on agentsmith-runtime as a package" in result.stdout, result.stdout + result.stderr
    assert not (repo / "runtime").exists()
    assert not (repo / "scripts").exists()

