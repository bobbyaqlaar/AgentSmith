"""
scripts/test/test_ai_stack_upgrade.py — `ai-stack-upgrade` commits what it
vendors, including files the tenant has never had.

Its "anything to commit?" check was `git diff --quiet`, which ignores untracked
files. A first-time vendor — runtime/ on a tenant onboarded before runtime/ was
vendored (KYC Sentinel, AqlaarTeleologyStudio's first pass), or a newly shipped
base fixture — copied the files, printed "No changes", and committed nothing.

The function lives inside install-ai-stack.sh; it is extracted and sourced on
its own so the test does not run the installer.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


def _function_source() -> str:
    text = (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")
    m = re.search(r"^function ai-stack-upgrade\(\) \{\n.*?^\}\n", text, re.S | re.M)
    assert m, "ai-stack-upgrade not found in install-ai-stack.sh"
    return m.group(0)


# The function ships inside the managed block written to ~/.zshrc, so zsh is the
# shell it actually runs in. Its glob semantics differ in a way that matters: an
# unmatched glob in a `for` aborts the whole function.
SHELLS = [s for s in ("bash", "zsh") if shutil.which(s)]


def _run_upgrade(shell: str, repo: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    script = tmp_path / "upgrade.sh"
    script.write_text(_function_source() + "\nai-stack-upgrade --to 9.9.9\n")
    return subprocess.run([shell, str(script)], cwd=repo, capture_output=True, text=True, check=False)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        check=True, capture_output=True, text=True,
    ).stdout


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("current_version", ["1.0.0", "9.9.9"])
def test_first_time_vendored_files_are_committed(tmp_path, monkeypatch, current_version, shell):
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

    result = _run_upgrade(shell, repo, tmp_path)

    assert "No changes" not in result.stdout, result.stdout
    tracked = set(_git(repo, "ls-files").split())
    assert "runtime/judging.py" in tracked, result.stdout + result.stderr
    assert "fixtures/security/control_registry.json" in tracked
    assert "fixtures/rag_poison_base.json" in tracked
    assert _git(repo, "status", "--porcelain") == ""
    # The lint-isolation config is regenerated to cover what was vendored.
    assert '"judging.py"' in (repo / "runtime" / "ruff.toml").read_text()
    assert '"run-evals.py"' in (repo / "scripts" / "ruff.toml").read_text()


@pytest.mark.parametrize("shell", SHELLS)
def test_upgrade_spares_a_tenants_own_scripts_test_and_runtime_package(tmp_path, monkeypatch, shell):
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

    result = _run_upgrade(shell, repo, tmp_path)

    assert (repo / "scripts" / "test" / "test_release.py").exists(), result.stdout
    assert not (repo / "scripts" / "test" / "test_framework.py").exists()
    assert not (repo / "runtime" / "llm_gateway.py").exists()
    assert "not AgentSmith's" in result.stdout
    assert "runtime/wip.py" not in _git(repo, "ls-files"), "a tenant's own runtime/ was swept into the commit"



@pytest.mark.parametrize("shell", SHELLS)
def test_upgrade_without_base_fixtures_installed_still_completes(tmp_path, monkeypatch, shell):
    """An install that predates base-fixture vendoring has none. Under zsh a
    glob over them aborted the function before it committed anything."""
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

    result = _run_upgrade(shell, repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "scripts/run-evals.py" in _git(repo, "ls-files"), result.stdout + result.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_upgrade_prunes_framework_internal_runtime_tests(tmp_path, monkeypatch, shell):
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

    result = _run_upgrade(shell, repo, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (repo / "runtime" / "test").iterdir()) == ["test_hitl_gate.py"]
    tracked = _git(repo, "ls-files")
    assert "runtime/test/test_pg_pool.py" not in tracked
    assert "runtime/test/test_hitl_gate.py" in tracked
