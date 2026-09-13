"""
scripts/test/test_scratch_tenants.py — the scratch-tenants pipeline
(.github/workflows/scratch-tenants.yml, .github/scratch-tenants/reprovision.sh,
docs/scratch-tenants.md).

The workflow itself only runs on GitHub with a PAT. What can be pinned here:
the re-provision script removes exactly what provisioning owns and keeps what
the tenant owns, it fails when the installed hook cannot provision, and the
workflow's matrix stays in step with the stacks and CI workflow names it waits
on — a renamed `name:` in a ci-*.yml would otherwise leave the job polling for
a run that never appears.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / ".github" / "scratch-tenants" / "reprovision.sh"
WORKFLOW = REPO / ".github" / "workflows" / "scratch-tenants.yml"

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="git and bash required"
)


def test_the_matrix_covers_every_stack_and_waits_on_its_real_ci_name():
    import sys

    sys.path.insert(0, str(REPO))
    from runtime.cli import STACKS

    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["reprovision"]
    matrix = job["strategy"]["matrix"]["include"]
    assert {m["stack"] for m in matrix} == set(STACKS)
    for m in matrix:
        template = REPO / "workflow-templates" / f"ci-{m['stack']}.yml"
        ci_name = yaml.safe_load(template.read_text(encoding="utf-8"))["name"]
        assert m["ci"] == ci_name, f"{m['stack']}: the job would wait for {m['ci']!r}, CI is named {ci_name!r}"


def test_the_commit_step_disarms_the_installed_hooks():
    """The installer arms ~/.git_templates, whose post-commit pushes and tags."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git -c core.hooksPath=/dev/null commit" in text


def _install(home: Path, monkeypatch, *, with_runtime: bool = True) -> None:
    """A complete ~/.agent-framework and ~/.git_templates, as install-ai-stack.sh
    lays them out. Complete matters: reprovision.sh fails on ANY hook warning, so
    a partial fake install is correctly reported as a broken onboarding."""
    import sys

    fw = home / ".agent-framework"
    ignore = shutil.ignore_patterns("__pycache__", ".hitl_blobs")
    shutil.copytree(REPO / "scripts", fw / "scripts", ignore=ignore)
    if with_runtime:
        shutil.copytree(REPO / "runtime", fw / "runtime", ignore=ignore)
    shutil.copytree(REPO / "fixtures" / "security", fw / "fixtures" / "security")
    shutil.copytree(REPO / "workflow-templates", fw / "workflow-templates")
    shutil.copytree(REPO / ".github" / "actions", fw / "github-actions")
    (fw / "templates").mkdir()
    shutil.copy(REPO / "templates" / "agent-rules.yaml", fw / "templates" / "agent-rules.yaml")
    hooks = home / ".git_templates" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(REPO / "hooks" / "post-checkout", hooks / "post-checkout")
    # The hook runs generate-ide-config.py with `python3`, which needs pyyaml —
    # this interpreter has it; a bare system python3 may not.
    shim = home.parent / "bin"
    shim.mkdir(exist_ok=True)
    if not (shim / "python3").exists():
        (shim / "python3").symlink_to(sys.executable)
    monkeypatch.setenv("PATH", f"{shim}:{__import__('os').environ['PATH']}")


def _stale_ts_tenant(tmp_path: Path) -> Path:
    repo = tmp_path / "tenant"
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(repo)], check=True)
    (repo / "package.json").write_text('{"name": "t", "scripts": {"test": "vitest run"}}\n')
    (repo / "src").mkdir()
    (repo / "src" / "app.ts").write_text("export {}\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "release.mjs").write_text("// the tenant's own\n")
    (repo / "scripts" / "run-security-checks.py").write_text("# stale vendored copy\n")
    (repo / "runtime").mkdir()
    (repo / "runtime" / "llm_gateway.py").write_text("# stale\n")
    (repo / "runtime" / "removed_upstream.py").write_text("# gone from the framework\n")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci-ts-react.yml").write_text("name: stale\n")
    (repo / ".agent-rfc" / "security").mkdir(parents=True)
    (repo / ".agent-rfc" / "security" / "risk_register.yaml").write_text("# authored by the tenant\n")
    (repo / ".agent-rfc" / "fixtures").mkdir()
    (repo / ".agent-rfc" / "fixtures" / "knowledge_graph.json").write_text("{}\n")
    return repo


@needs_git
def test_reprovision_replaces_what_provisioning_owns_and_keeps_the_tenants(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _install(home, monkeypatch)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)
    repo = _stale_ts_tenant(tmp_path)

    result = subprocess.run(["bash", str(SCRIPT), "ts-react", str(repo)], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stdout + result.stderr
    # Tenant-owned: untouched.
    assert (repo / "src" / "app.ts").exists()
    assert (repo / "scripts" / "release.mjs").read_text() == "// the tenant's own\n"
    assert (repo / ".agent-rfc" / "security" / "risk_register.yaml").read_text() == "# authored by the tenant\n"
    # Provisioning-owned: rebuilt from the install, stale files gone.
    assert (repo / "scripts" / "run-security-checks.py").read_text() == (
        REPO / "scripts" / "run-security-checks.py"
    ).read_text()
    assert not (repo / "runtime" / "removed_upstream.py").exists()
    assert "name: stale" not in (repo / ".github" / "workflows" / "ci-ts-react.yml").read_text()
    assert (repo / ".agenticframework" / "enabled").exists()


@needs_git
def test_reprovision_fails_when_the_install_cannot_provision(tmp_path, monkeypatch):
    """An install missing runtime/ makes the hook warn and carry on. For a
    tenant that is a broken onboarding, so the pipeline must go red on it."""
    home = tmp_path / "home"
    _install(home, monkeypatch, with_runtime=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)
    repo = _stale_ts_tenant(tmp_path)

    result = subprocess.run(["bash", str(SCRIPT), "ts-react", str(repo)], capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert "could not fully provision" in result.stdout
