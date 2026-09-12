"""
scripts/test/test_vendored_lint_isolation.py — vendored framework code stays
out of a tenant's `ruff check .` / `ruff format --check .`, and the tenant's
own code does not.

AqlaarTeleologyStudio's lint step failed on 746 findings, 609 of them in the
vendored runtime/ and scripts/ — the framework's code graded by the tenant's
rules. The hook now writes a nested ruff.toml into each vendored directory that
extends the tenant's root config and excludes exactly the vendored files.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "hooks" / "post-checkout"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None or shutil.which("ruff") is None,
    reason="git, bash and ruff required",
)

# Deliberately violates the tenant's extended rules (UP045) and is mis-formatted.
VIOLATION = "from typing import Optional\ndef f(x:Optional[int])->Optional[int]:\n    return x\n"


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    fw = tmp_path / "home" / ".agent-framework"
    (fw / "scripts" / "security").mkdir(parents=True)
    (fw / "scripts" / "run-security-checks.py").write_text(VIOLATION)
    (fw / "scripts" / "security" / "runner.py").write_text(VIOLATION)
    (fw / "runtime").mkdir()
    (fw / "runtime" / "llm_gateway.py").write_text(VIOLATION)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / ".agenticframework").mkdir()
    (repo / ".agenticframework" / "enabled").touch()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0"\n[tool.ruff.lint]\nextend-select = ["UP"]\n'
    )
    return repo


def _hook(repo: Path) -> None:
    result = subprocess.run(["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def _flagged(repo: Path, *args: str) -> set[str]:
    out = subprocess.run(["ruff", *args], cwd=repo, capture_output=True, text=True, check=False).stdout
    return {line.split(":", 1)[0] for line in out.splitlines() if ".py:" in line or line.startswith("Would reformat")}


def test_vendored_files_are_excluded_but_the_tenants_own_files_in_the_same_dir_are_not(tenant):
    (tenant / "scripts").mkdir()
    (tenant / "scripts" / "tool.py").write_text(VIOLATION)  # the tenant's own
    (tenant / "app.py").write_text(VIOLATION)

    _hook(tenant)

    checked = _flagged(tenant, "check", ".", "--output-format", "concise")
    assert checked == {"app.py", "scripts/tool.py"}, checked
    reformat = subprocess.run(
        ["ruff", "format", "--check", "."], cwd=tenant, capture_output=True, text=True, check=False
    ).stdout
    assert "scripts/tool.py" in reformat and "app.py" in reformat
    assert "runtime/" not in reformat and "run-security-checks.py" not in reformat, reformat


def test_an_existing_directory_config_is_never_overwritten(tenant):
    (tenant / "scripts").mkdir()
    (tenant / "scripts" / "ruff.toml").write_text("# the tenant's own\n")

    _hook(tenant)

    assert (tenant / "scripts" / "ruff.toml").read_text() == "# the tenant's own\n"


def test_the_framework_itself_carries_no_such_config():
    """Written into tenants at vendor time only. In the framework's own tree the
    same file would silently exclude runtime/ and scripts/ from its lint gate."""
    assert not (REPO / "runtime" / "ruff.toml").exists()
    assert not (REPO / "scripts" / "ruff.toml").exists()
