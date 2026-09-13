"""
scripts/test/test_ci_package_managers.py — the CI templates install with the
package manager the tenant's lockfile names.

ci-ts-react.yml assumed npm (`cache: npm`, `npm ci`), so a pnpm tenant failed
setup-node before any check ran; ci-python-fastapi.yml installed only a
requirements.txt, so a uv tenant's tests failed at import. The scratch apps
ts-react-pnpm and python-uv (docs/scratch-tenants.md) prove the fix on GitHub.
This file is the cheap layer: it runs the templates' OWN `run:` scripts, in
order, against a stub project with every package-manager binary replaced by a
shim that records its arguments — so what is asserted is what the runner would
execute, not a regex over the YAML.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "workflow-templates"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

SHIMMED = ("npm", "npx", "pnpm", "pip", "uv")


def _steps(template: str) -> list[dict]:
    doc = yaml.safe_load((TEMPLATES / template).read_text(encoding="utf-8"))
    return doc["jobs"]["guardrails"]["steps"]


def _step(template: str, name: str) -> dict:
    return next(s for s in _steps(template) if s.get("name") == name)


class Runner:
    """Runs `run:` blocks the way Actions does: bash -e, GITHUB_ENV applied
    between steps, GITHUB_OUTPUT collected per step."""

    def __init__(self, project: Path, tmp: Path) -> None:
        self.project = project
        self.tmp = tmp
        self.log = tmp / "calls.log"
        self.log.write_text("")
        shims = tmp / "shims"
        shims.mkdir()
        for tool in SHIMMED:
            (shims / tool).write_text(f'#!/bin/sh\necho "{tool} $*" >> "{self.log}"\n')
            (shims / tool).chmod(0o755)
        self.env_file = tmp / "github_env"
        self.env_file.write_text("")
        self.base_env = {**os.environ, "PATH": f"{shims}{os.pathsep}{os.environ['PATH']}", "RUNNER_TEMP": str(tmp)}

    def run(self, script: str) -> tuple[subprocess.CompletedProcess, dict[str, str]]:
        out = self.tmp / "github_output"
        out.write_text("")
        env = dict(self.base_env, GITHUB_ENV=str(self.env_file), GITHUB_OUTPUT=str(out))
        for line in self.env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            env[key] = value
        result = subprocess.run(
            ["bash", "-e", "-c", script], cwd=self.project, env=env,
            capture_output=True, text=True, check=False,
        )
        outputs = dict(ln.partition("=")[::2] for ln in out.read_text().splitlines())
        return result, outputs

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()


def _ts_project(tmp_path: Path, lockfile: str | None, package_manager: str | None = None) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    pkg = {"name": "t", "scripts": {"test": "vitest run"}}
    if package_manager:
        pkg["packageManager"] = package_manager
    (project / "package.json").write_text(json.dumps(pkg))
    if lockfile:
        (project / lockfile).write_text("")
    return project


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node required")

TS_STEPS = ("Detect package manager", "Install dependencies", "Type check", "Lint", "Unit tests")


def _run_ts(project: Path, tmp_path: Path) -> tuple[Runner, dict[str, str]]:
    runner = Runner(project, tmp_path)
    outputs: dict[str, str] = {}
    for name in TS_STEPS:
        result, out = runner.run(_step("ci-ts-react.yml", name)["run"])
        assert result.returncode == 0, f"{name}: {result.stdout}{result.stderr}"
        outputs |= out
    return runner, outputs


@needs_node
def test_a_pnpm_tenant_is_installed_checked_and_tested_with_pnpm_only(tmp_path):
    runner, outputs = _run_ts(_ts_project(tmp_path, "pnpm-lock.yaml", "pnpm@12.4.1"), tmp_path)

    assert outputs["pm"] == "pnpm"
    assert outputs["pnpm_version"] == "", "packageManager pins it; a second version makes pnpm/action-setup fail"
    assert runner.calls() == [
        "pnpm install --frozen-lockfile",
        "pnpm exec tsc -b --noEmit",
        "pnpm run --if-present lint",
        "pnpm test",
    ]


@needs_node
def test_a_pnpm_tenant_without_packagemanager_gets_a_version(tmp_path):
    _, outputs = _run_ts(_ts_project(tmp_path, "pnpm-lock.yaml"), tmp_path)

    assert outputs["pm"] == "pnpm"
    assert outputs["pnpm_version"]


@needs_node
def test_an_npm_tenant_still_uses_npm(tmp_path):
    runner, outputs = _run_ts(_ts_project(tmp_path, "package-lock.json"), tmp_path)

    assert outputs["pm"] == "npm"
    assert runner.calls() == [
        "npm ci",
        "npx --no-install tsc -b --noEmit",
        "npm run --if-present lint",
        "npm test",
    ]


@pytest.mark.parametrize(("lockfile", "message"), [("yarn.lock", "not supported"), (None, "no lockfile")])
def test_an_unsupported_or_missing_lockfile_fails_by_name(tmp_path, lockfile, message):
    runner = Runner(_ts_project(tmp_path, lockfile), tmp_path)

    result, _ = runner.run(_step("ci-ts-react.yml", "Detect package manager")["run"])

    assert result.returncode == 1
    assert message in result.stdout


def test_setup_node_caches_for_the_detected_manager_after_pnpm_is_on_path():
    names = [s.get("name") for s in _steps("ci-ts-react.yml")]
    assert names.index("Detect package manager") < names.index("Setup pnpm") < names.index("Setup Node")
    pnpm = _step("ci-ts-react.yml", "Setup pnpm")
    assert pnpm["if"] == "steps.pm.outputs.pm == 'pnpm'"
    assert _step("ci-ts-react.yml", "Setup Node")["with"]["cache"] == "${{ steps.pm.outputs.pm }}"


# ── Python ───────────────────────────────────────────────────────────────────


def _py_calls(tmp_path: Path, files: list[str]) -> list[str]:
    project = tmp_path / "project"
    project.mkdir()
    for name in files:
        (project / name).write_text("")
    runner = Runner(project, tmp_path)
    result, _ = runner.run(_step("ci-python-fastapi.yml", "Install dependencies")["run"])
    assert result.returncode == 0, result.stdout + result.stderr
    # `python -m pip install --upgrade pip` is not a shim call; the tool
    # installs at the end are the same in every case.
    return [c for c in runner.calls() if not c.startswith("pip install pytest ")]


@pytest.fixture()
def no_real_pip_upgrade(tmp_path, monkeypatch):
    """`python -m pip` bypasses the pip shim; point `python` at a no-op."""
    bin_dir = tmp_path / "pybin"
    bin_dir.mkdir()
    (bin_dir / "python").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "python").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def test_a_uv_tenant_installs_its_locked_dependencies(tmp_path, no_real_pip_upgrade):
    calls = _py_calls(tmp_path, ["pyproject.toml", "uv.lock"])

    assert calls == [
        "pip install uv",
        f"uv export --frozen --no-hashes --format requirements-txt -o {tmp_path}/uv-requirements.txt",
        f"pip install -r {tmp_path}/uv-requirements.txt",
    ]


def test_requirements_txt_wins_and_uv_is_not_touched(tmp_path, no_real_pip_upgrade):
    assert _py_calls(tmp_path, ["requirements.txt", "pyproject.toml", "uv.lock"]) == ["pip install -r requirements.txt"]


def test_a_project_with_neither_installs_only_the_tools(tmp_path, no_real_pip_upgrade):
    assert _py_calls(tmp_path, ["pyproject.toml"]) == []
