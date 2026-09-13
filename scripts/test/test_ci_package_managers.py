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

ACTION = REPO / ".github" / "actions" / "install-python-deps" / "action.yml"


def _action_script() -> str:
    steps = yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"]
    assert len(steps) == 1
    return steps[0]["run"]


def test_both_python_callers_install_through_the_one_action():
    """ci-python-fastapi.yml and eval-security.yml each carried a copy of the
    install guard, and only one learned about uv."""
    ci = _steps("ci-python-fastapi.yml")
    assert any(s.get("uses") == "./.github/actions/install-python-deps" for s in ci)
    for path in (TEMPLATES / "eval-security.yml", REPO / ".github" / "workflows" / "eval-security.yml"):
        steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["security"]["steps"]
        assert any(s.get("uses") == "./.github/actions/install-python-deps" for s in steps), path
    for text in (s.get("run", "") for s in ci):
        assert "requirements.txt" not in text and "uv export" not in text, "a second copy of the install"


@pytest.fixture()
def no_real_pip_upgrade(tmp_path, monkeypatch):
    """`python -m pip` bypasses the pip shim; point `python` at a no-op."""
    bin_dir = tmp_path / "pybin"
    bin_dir.mkdir()
    (bin_dir / "python").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "python").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def _install(tmp_path: Path, files: list[str]) -> tuple[subprocess.CompletedProcess, list[str]]:
    project = tmp_path / "project"
    project.mkdir()
    for name in files:
        (project / name).write_text("")
    runner = Runner(project, tmp_path)
    result, _ = runner.run(_action_script())
    assert result.returncode == 0, result.stdout + result.stderr
    return result, runner.calls()


def test_a_uv_tenant_installs_its_lock_and_a_stale_lock_fails(tmp_path, no_real_pip_upgrade):
    _, calls = _install(tmp_path, ["pyproject.toml", "uv.lock"])

    pin, export, install = calls
    assert pin.startswith("pip install uv=="), "uv must be pinned, like ruff"
    # --locked fails when uv.lock no longer matches pyproject.toml; --frozen
    # exported the stale lock and silently dropped the new dependency.
    assert export == f"uv export --locked --no-hashes --format requirements-txt -o {tmp_path}/uv-requirements.txt"
    assert install == f"pip install -r {tmp_path}/uv-requirements.txt"


def test_requirements_txt_wins_and_uv_is_not_touched(tmp_path, no_real_pip_upgrade):
    _, calls = _install(tmp_path, ["requirements.txt", "pyproject.toml", "uv.lock"])
    assert calls == ["pip install -r requirements.txt"]


@pytest.mark.parametrize("manifest", ["pyproject.toml", "Pipfile"])
def test_a_project_whose_dependencies_cannot_be_installed_is_told_so(tmp_path, no_real_pip_upgrade, manifest):
    """Requirement: a Python project CI cannot install must not look installed.
    It still passes — the tools alone may be enough — but the run says so."""
    result, calls = _install(tmp_path, [manifest])
    assert calls == []
    assert "::warning title=Project dependencies not installed::" in result.stdout


def test_a_repo_with_no_python_manifest_gets_no_warning(tmp_path, no_real_pip_upgrade):
    """eval-security.yml runs on Go and TS tenants too; they have nothing to install."""
    result, calls = _install(tmp_path, ["go.mod"])
    assert calls == [] and "::warning" not in result.stdout


# ── The hook's test command and the CI install agree on the tool ─────────────
#
# The same lockfile precedence lives in bash (hooks/post-checkout, which writes
# the agent rules' test command) and in the CI templates. Neither can import
# the other, so this RUNS both sides over the same projects.

HOOK = REPO / "hooks" / "post-checkout"


def _hook_test_cmd(project: Path) -> str:
    text = HOOK.read_text(encoding="utf-8")
    block = text[text.index("# ── Detect stack"):text.index('echo "🔧 AgentSmith: Detected stack')]
    result = subprocess.run(
        ["bash", "-c", f'REPO_ROOT="{project}"\n{block}\nprintf "%s" "$TEST_CMD"'],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _project(tmp_path: Path, files: list[str]) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    for name in files:
        (project / name).write_text("{}" if name == "package.json" else "")
    return project


@needs_node
@pytest.mark.parametrize(
    ("files", "tool"),
    [
        (["package.json", "package-lock.json"], "npm"),
        (["package.json", "pnpm-lock.yaml"], "pnpm"),
        (["package.json", "pnpm-lock.yaml", "package-lock.json"], "pnpm"),
        (["package.json", "package-lock.json", "yarn.lock"], "npm"),
        (["package.json", "yarn.lock"], None),
        (["package.json", "bun.lockb"], None),
    ],
)
def test_hook_and_ts_template_pick_the_same_package_manager(tmp_path, files, tool):
    project = _project(tmp_path, files)
    hook = _hook_test_cmd(project)
    result, outputs = Runner(project, tmp_path).run(_step("ci-ts-react.yml", "Detect package manager")["run"])
    if tool is None:
        assert result.returncode == 1, "the template must refuse an unsupported lockfile"
        assert hook.split()[1] in {"yarn", "bun"}, f"the hook claims {hook!r} for a {files[-1]} project"
    else:
        assert outputs["pm"] == tool
        assert hook == f"CI=true {tool} test"


@pytest.mark.parametrize(
    ("files", "uses_uv"),
    [
        (["pyproject.toml", "uv.lock"], True),
        (["requirements.txt", "uv.lock"], False),
        (["requirements.txt"], False),
        (["pyproject.toml"], False),
    ],
)
def test_hook_and_python_install_agree_on_uv(tmp_path, no_real_pip_upgrade, files, uses_uv):
    project = _project(tmp_path, files)
    runner = Runner(project, tmp_path)
    runner.run(_action_script())
    assert any(c.startswith("uv ") for c in runner.calls()) is uses_uv
    assert (_hook_test_cmd(project) == "uv run pytest") is uses_uv


def test_the_pnpm_fallback_is_the_version_the_scratch_tenant_proves():
    pkg = json.loads((REPO / ".github/scratch-tenants/apps/ts-react-pnpm/package.json").read_text(encoding="utf-8"))
    proven = pkg["packageManager"].removeprefix("pnpm@")
    detect = _step("ci-ts-react.yml", "Detect package manager")["run"]
    assert f"version={proven}" in detect, f"the template's fallback pnpm is not the proven {proven}"
