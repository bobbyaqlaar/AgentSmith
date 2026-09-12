"""
scripts/test/test_installed_runtime_tenant.py — a tenant that depends on
agentsmith-runtime as a package is not vendored into.

Verified on a hook-free clone of KYC Sentinel (2026-09-13), which pins
`agentsmith-runtime @ git+https://…@v1.3.0` and runs the harness from a
framework checkout in its own ci.yml. The hook vendored runtime/ at its repo
root — shadowing the pinned package for demo.py and worker.py, which run from
there — merged 44 framework scripts into its own scripts/, and wrote seven
generated workflows including cd-production.yml, all built for a vendored
layout the repo does not have. A re-clone arms the hook (init.templateDir), so
this was one `git clone` away.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "post-checkout"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


@pytest.fixture()
def framework_home(tmp_path, monkeypatch):
    fw = tmp_path / "home" / ".agent-framework"
    (fw / "scripts").mkdir(parents=True)
    (fw / "scripts" / "run-security-checks.py").write_text("# harness\n")
    (fw / "runtime" / "test").mkdir(parents=True)
    (fw / "runtime" / "llm_gateway.py").write_text("# gateway\n")
    (fw / "fixtures" / "security").mkdir(parents=True)
    (fw / "fixtures" / "security" / "control_registry.json").write_text("[]\n")
    (fw / "fixtures" / "rag_poison_base.json").write_text("[]\n")
    shutil.copytree(REPO / "workflow-templates", fw / "workflow-templates")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)
    return fw


def _tenant(tmp_path: Path, manifest: str, content: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "enabled").touch()
    (repo / manifest).write_text(content)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "pin_eval_outputs.py").write_text("# the tenant's own\n")
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, check=False)


@pytest.mark.parametrize(
    ("manifest", "content"),
    [
        ("requirements.txt", "agentsmith-runtime[temporal] @ git+https://github.com/bobbyaqlaar/AgentSmith@v1.3.0\n"),
        ("pyproject.toml", '[project]\nname = "t"\ndependencies = [\n  "agentsmith-runtime>=1.3",\n]\n'),
    ],
)
def test_a_package_consumer_is_not_vendored_into(framework_home, tmp_path, manifest, content):
    repo = _tenant(tmp_path, manifest, content)

    result = _run(repo)

    assert result.returncode == 0, result.stderr
    assert not (repo / "runtime").exists(), "runtime/ at the root would shadow the pinned package"
    assert sorted(p.name for p in (repo / "scripts").iterdir()) == ["pin_eval_outputs.py"]
    assert not (repo / "fixtures").exists()
    assert not (repo / ".github" / "workflows").exists()
    assert "installed mode" in result.stdout


def test_a_vendored_tenant_is_still_vendored(framework_home, tmp_path):
    """The guard keys on the dependency, not on Python: a plain FastAPI tenant
    is vendored exactly as before."""
    repo = _tenant(tmp_path, "requirements.txt", "fastapi\n")

    result = _run(repo)

    assert result.returncode == 0, result.stderr
    assert (repo / "runtime" / "llm_gateway.py").exists()
    assert (repo / "scripts" / "run-security-checks.py").exists()
    assert (repo / ".github" / "workflows" / "ci-python-fastapi.yml").exists()
    assert "installed mode" not in result.stdout
