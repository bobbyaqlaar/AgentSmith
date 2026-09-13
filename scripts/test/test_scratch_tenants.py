"""
scripts/test/test_scratch_tenants.py — the scratch-tenants pipeline
(.github/scratch-tenants/{apps/,build.sh}, .github/workflows/scratch-tenants.yml,
docs/scratch-tenants.md).

Two layers. The workflow proves on GitHub that each built tenant's own CI goes
green; that needs a PAT and minutes. This file is the cheap layer that runs on
every Self-Test: it BUILDS every scratch app with the real post-checkout hook
into a temp directory and checks the result offline, so most onboarding breaks
fail here, before anything is pushed to a scratch repo. It also pins build.sh's
safety checks and keeps the workflow matrix in step with the stacks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRATCH = REPO / ".github" / "scratch-tenants"
APPS = SCRATCH / "apps"
BUILD = SCRATCH / "build.sh"
WORKFLOW = REPO / ".github" / "workflows" / "scratch-tenants.yml"
BOT = "AgentSmith scratch-tenants"

sys.path.insert(0, str(REPO))
from runtime.cli import STACKS

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="git and bash required"
)


# ── The workflow and the app sources agree with the stacks ───────────────────


def _matrix() -> list[dict]:
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build"]
    return job["strategy"]["matrix"]["include"]


def test_every_stack_has_an_app_and_a_matrix_entry_waiting_on_its_real_ci():
    assert {m["stack"] for m in _matrix()} == set(STACKS)
    assert {p.name for p in APPS.iterdir() if p.is_dir()} == set(STACKS)
    for m in _matrix():
        template = REPO / "workflow-templates" / f"ci-{m['stack']}.yml"
        ci_name = yaml.safe_load(template.read_text(encoding="utf-8"))["name"]
        assert m["ci"] == ci_name, f"{m['stack']}: the job would wait for {m['ci']!r}, CI is named {ci_name!r}"


@pytest.mark.parametrize(
    ("stack", "marker"),
    [("ts-react", "package.json"), ("go", "go.mod"), ("python-fastapi", "requirements.txt")],
)
def test_each_app_is_detected_as_its_own_stack(stack, marker):
    """The hook picks the stack from root files, package.json first."""
    root = APPS / stack
    assert (root / marker).is_file()
    others = {"package.json", "go.mod", "requirements.txt", "pyproject.toml", "Pipfile"} - {marker}
    assert not [o for o in others if (root / o).exists()], f"{stack} app would be detected as another stack"


def test_apps_carry_nothing_provisioning_generates():
    """App source is only what a tenant writes. Generated files here would mask
    the hook failing to produce them."""
    generated = {
        ".github", "runtime", "fixtures", ".agents", ".cursorrules", "CLAUDE.md", "AGENTS.md",
        "GEMINI.md", ".agenticframework", "SCRATCH_TENANT.md", ".agent-history.log",
    }
    for app in (p for p in APPS.iterdir() if p.is_dir()):
        present = {p.name for p in app.iterdir()} & generated
        assert not present, f"apps/{app.name} contains generated paths: {present}"
        rfc = app / ".agent-rfc"
        if rfc.exists():
            assert {p.name for p in rfc.iterdir()} == {"security"}, f"apps/{app.name}/.agent-rfc beyond security/"


def test_the_commit_step_disarms_hooks_and_uses_the_author_build_sh_expects():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git -c core.hooksPath=/dev/null commit" in text
    assert f'git config user.name  "{BOT}"' in text
    assert f'WORKFLOW_AUTHOR="{BOT}"' in BUILD.read_text(encoding="utf-8")


# ── Building for real, offline ───────────────────────────────────────────────


@pytest.fixture()
def install(tmp_path, monkeypatch):
    """A complete ~/.agent-framework and ~/.git_templates, as install-ai-stack.sh
    lays them out. Complete matters: build.sh fails on ANY hook warning."""
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    ignore = shutil.ignore_patterns("__pycache__", ".hitl_blobs")
    shutil.copytree(REPO / "scripts", fw / "scripts", ignore=ignore)
    shutil.copytree(REPO / "runtime", fw / "runtime", ignore=ignore)
    shutil.copytree(REPO / "fixtures" / "security", fw / "fixtures" / "security")
    for base in (REPO / "fixtures").glob("*_base.json"):
        shutil.copy(base, fw / "fixtures" / base.name)
    shutil.copytree(REPO / "workflow-templates", fw / "workflow-templates")
    shutil.copytree(REPO / ".github" / "actions", fw / "github-actions")
    (fw / "templates").mkdir()
    shutil.copy(REPO / "templates" / "agent-rules.yaml", fw / "templates" / "agent-rules.yaml")
    hooks = home / ".git_templates" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(REPO / "hooks" / "post-checkout", hooks / "post-checkout")
    # python3 with pyyaml for generate-ide-config.py (a bare system python3 may
    # lack it), and a normal pycache location so a .pyc regression is visible.
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "python3").symlink_to(sys.executable)
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)
    monkeypatch.delenv("PYTHONPYCACHEPREFIX", raising=False)
    monkeypatch.delenv("SCRATCH_TENANTS_ALLOW_MANUAL_HEAD", raising=False)
    return home


def _build(stack: str, target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(BUILD), stack, str(target)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )


def _init(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(target)], check=True)


def _commit(target: Path, author: str) -> None:
    subprocess.run(["git", "-C", str(target), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "-c", f"user.name={author}", "-c", "user.email=a@x",
         "commit", "-q", "-m", "commit"],
        check=True,
    )


@needs_git
@pytest.mark.parametrize("stack", STACKS)
def test_each_app_builds_into_a_complete_tenant_offline(stack, install, tmp_path):
    target = tmp_path / "tenant"

    result = _build(stack, target)

    assert result.returncode == 0, result.stdout + result.stderr
    # The app, verbatim.
    for src in (p for p in (APPS / stack).rglob("*") if p.is_file()):
        rel = src.relative_to(APPS / stack)
        assert (target / rel).read_bytes() == src.read_bytes(), f"{rel} differs from the app source"
    # What provisioning must have produced.
    assert (target / ".github" / "workflows" / f"ci-{stack}.yml").is_file()
    assert (target / ".github" / "actions" / "gcp-auth" / "action.yml").is_file()
    assert (target / "scripts" / "run-security-checks.py").is_file()
    assert sorted(p.name for p in (target / "runtime" / "test").iterdir()) == sorted([
        "conftest.py", "test_hitl_gate.py", "test_dead_letter.py",
        "test_llm_gateway_budget.py", "test_self_correction.py",
    ])
    assert (target / "CLAUDE.md").is_file()
    assert (target / "SCRATCH_TENANT.md").is_file()
    assert not list(target.rglob("*.pyc"))


@needs_git
def test_a_stale_file_in_the_target_does_not_survive_a_build(install, tmp_path):
    target = tmp_path / "tenant"
    _init(target)
    (target / "security-evidence").mkdir()
    (target / "security-evidence" / "report.json").write_text("{}\n")
    _commit(target, BOT)

    result = _build("go", target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (target / "security-evidence").exists()


@needs_git
def test_a_hand_edit_in_the_scratch_repo_fails_the_build(install, tmp_path):
    """Overwriting it silently is exactly the quiet loss this pipeline exists
    to prevent; the change belongs in apps/<stack>/."""
    target = tmp_path / "tenant"
    _init(target)
    (target / "main.go").write_text("package main\n")
    _commit(target, "Someone")

    result = _build("go", target)

    assert result.returncode == 1
    assert "edited directly" in result.stdout + result.stderr
    assert (target / "main.go").read_text() == "package main\n", "nothing may be touched before the check"


@needs_git
def test_the_build_fails_when_the_install_cannot_provision(install, tmp_path):
    shutil.rmtree(install / ".agent-framework" / "runtime")

    result = _build("python-fastapi", tmp_path / "tenant")

    assert result.returncode == 1
    assert "could not fully provision" in result.stdout


@needs_git
def test_the_build_fails_if_the_hook_rewrites_gitignore(install, tmp_path, monkeypatch):
    """A repo the hook cannot confirm is private gets IDE config ignored. For
    the go app, which has no .gitignore, the hook CREATES one — the first
    version of this check only compared existing files and missed it."""
    target = tmp_path / "tenant"
    _init(target)
    subprocess.run(
        ["git", "-C", str(target), "remote", "add", "origin", "https://github.com/example/scratch.git"], check=True
    )
    nogh = tmp_path / "nogh"
    nogh.mkdir()
    (nogh / "gh").write_text("#!/bin/sh\nexit 1\n")
    (nogh / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{nogh}{os.pathsep}{os.environ['PATH']}")

    result = _build("go", target)

    assert result.returncode == 1
    assert "changed .gitignore" in result.stdout + result.stderr
