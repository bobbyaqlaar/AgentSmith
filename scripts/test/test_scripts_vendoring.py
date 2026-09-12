"""
scripts/test/test_scripts_vendoring.py — post-checkout vendors scripts/ into
a fresh tenant.

Found onboarding AqlaarTeleologyStudio (2026-09-12): every generated CI
workflow calls `python3 scripts/<name>.py` directly from the tenant's OWN
repo, but nothing ever copied scripts/ there. The hook's own fallback to
$SCRIPTS_DIR only covers ITS OWN calls (generate-ide-config.py,
map_codebase.py) during this one invocation — a GitHub Actions runner, or a
collaborator's machine with no ~/.agent-framework, has nothing to fall back
to. Every scripts/*.py step in every generated workflow failed with "No such
file", mostly silently since most of those steps are non-blocking.

Runs the real hook in a scratch repo with a fake $HOME, same approach as
test_security_pack_seeding.py.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / "hooks"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="git and bash required",
)


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """An opted-in scratch repo with a fake vendored ~/.agent-framework/scripts/,
    including a test/ subdir and a __pycache__ — the parts a tenant must NOT
    receive — alongside two real .py files it should."""
    home = tmp_path / "home"
    fw_scripts = home / ".agent-framework" / "scripts"
    fw_scripts.mkdir(parents=True)
    (fw_scripts / "map_codebase.py").write_text("# map_codebase\n")
    (fw_scripts / "_shared.py").write_text("# shared helpers\n")
    (fw_scripts / "test").mkdir()
    (fw_scripts / "test" / "test_map_codebase.py").write_text("# framework's own test\n")
    (fw_scripts / "__pycache__").mkdir()
    (fw_scripts / "__pycache__" / "map_codebase.cpython-311.pyc").write_bytes(b"\x00")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)

    work = tmp_path / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / ".agenticframework").mkdir()
    (work / ".agenticframework" / "enabled").touch()
    return work


def _run_post_checkout(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(HOOKS_DIR / "post-checkout")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_vendors_scripts_when_missing(tenant):
    result = _run_post_checkout(tenant)
    assert result.returncode == 0, result.stderr
    assert (tenant / "scripts" / "map_codebase.py").exists()
    assert (tenant / "scripts" / "_shared.py").exists()
    assert "Vendored scripts/" in result.stdout


def test_excludes_frameworks_own_test_suite_and_pycache(tenant):
    """A tenant runs its own tests, not AgentSmith's — scripts/test/ and any
    __pycache__ are framework-internal and must not ship into every tenant."""
    _run_post_checkout(tenant)
    assert not (tenant / "scripts" / "test").exists()
    assert not any((tenant / "scripts").rglob("__pycache__"))


def test_never_overwrites_an_existing_scripts_dir(tenant):
    """A tenant may have patched a vendored script — a routine `git checkout`
    firing this hook must not silently clobber that. Pulling in newer
    framework scripts is ai-stack-upgrade's job, deliberately."""
    scripts_dir = tenant / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "map_codebase.py").write_text("# tenant's own patched copy\n")

    result = _run_post_checkout(tenant)

    assert (scripts_dir / "map_codebase.py").read_text() == "# tenant's own patched copy\n"
    assert not (scripts_dir / "_shared.py").exists()
    assert "Vendored scripts/" not in result.stdout


def test_no_framework_scripts_installed_is_not_fatal(tmp_path, monkeypatch):
    """A machine whose install predates this step, or ran with an empty
    vendor cache, must still check out cleanly."""
    home = tmp_path / "home"
    (home / ".agent-framework").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    work = tmp_path / "repo"
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / ".agenticframework").mkdir()
    (work / ".agenticframework" / "enabled").touch()

    result = _run_post_checkout(work)

    assert result.returncode == 0, result.stderr
    assert not (work / "scripts").exists()
    assert "scripts/ not vendored" in result.stdout


def test_unopted_repo_is_not_vendored(tenant):
    """The opt-in gate still applies — an unrelated repo with history must
    not get scripts/ written into it."""
    subprocess.run(["git", "-C", str(tenant), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tenant), "-c", "user.email=t@e.com", "-c", "user.name=T",
         "commit", "-q", "-m", "initial"],
        check=True,
    )
    (tenant / ".agenticframework" / "enabled").unlink()

    result = _run_post_checkout(tenant)

    assert "not opted in" in result.stdout
    assert not (tenant / "scripts").exists()
