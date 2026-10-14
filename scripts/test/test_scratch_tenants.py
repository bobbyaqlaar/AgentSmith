"""
scripts/test/test_scratch_tenants.py — the scratch-tenants pipeline
(.github/scratch-tenants/{apps/,build.sh}, .github/workflows/scratch-tenants.yml,
docs/scratch-tenants.md).

Two layers. The workflow proves on GitHub that each built tenant's own CI goes
green; that needs a PAT and minutes. This file is the cheap layer that runs on
every Self-Test: it BUILDS every scratch app with the real `tenant init` into a
temp directory and checks the result offline, so most onboarding breaks
fail here, before anything is pushed to a scratch repo. It also pins build.sh's
safety checks and keeps the workflow matrix in step with the stacks.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
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


def test_every_app_has_a_matrix_entry_waiting_on_its_stacks_real_ci():
    """One entry per app, several apps per stack allowed; every stack covered."""
    matrix = _matrix()
    assert sorted(m["app"] for m in matrix) == sorted(p.name for p in APPS.iterdir() if p.is_dir())
    assert {m["stack"] for m in matrix} == set(STACKS)
    assert len({m["repo"] for m in matrix}) == len(matrix), "two apps would push to one scratch repo"
    for m in matrix:
        template = REPO / "workflow-templates" / f"ci-{m['stack']}.yml"
        ci_name = yaml.safe_load(template.read_text(encoding="utf-8"))["name"]
        assert m["ci"] == ci_name, f"{m['app']}: the job would wait for {m['ci']!r}, CI is named {ci_name!r}"


# What makes each scenario the scenario it claims to be. Without these the
# pnpm app could quietly regain a package-lock.json and prove nothing.
SCENARIOS = {
    "ts-react": {"has": ["package-lock.json", "scripts/release.mjs"], "lacks": ["pnpm-lock.yaml"]},
    "ts-react-pnpm": {"has": ["pnpm-lock.yaml"], "lacks": ["package-lock.json"]},
    "go": {"has": ["go.mod"], "lacks": [".gitignore"]},
    "python-fastapi": {"has": ["requirements.txt"], "lacks": ["pyproject.toml", "uv.lock"]},
    "python-uv": {"has": ["pyproject.toml", "uv.lock"], "lacks": ["requirements.txt"]},
}


def test_every_app_is_the_scenario_it_claims():
    assert set(SCENARIOS) == {p.name for p in APPS.iterdir() if p.is_dir()}
    for app, spec in SCENARIOS.items():
        for rel in spec["has"]:
            assert (APPS / app / rel).exists(), f"apps/{app} needs {rel}"
        for rel in spec["lacks"]:
            assert not (APPS / app / rel).exists(), f"apps/{app} must not have {rel}"
    pkg = json.loads((APPS / "ts-react-pnpm" / "package.json").read_text(encoding="utf-8"))
    assert pkg["packageManager"].startswith("pnpm@")
    assert "[tool.ruff]" in (APPS / "python-uv" / "pyproject.toml").read_text(encoding="utf-8")


# A scenario app is its base app with ONE thing changed. Everything else is a
# deliberate copy — each scratch repo must be a realistic standalone project —
# so it is pinned here instead: a fix to one copy that misses the other fails.
SCENARIO_BASE = {"ts-react-pnpm": "ts-react", "python-uv": "python-fastapi"}
SCENARIO_ONLY = {
    # The only paths each scenario may differ from its base in.
    "ts-react-pnpm": {"package-lock.json", "pnpm-lock.yaml", "package.json", "scripts/release.mjs"},
    "python-uv": {"requirements.txt", "pyproject.toml", "uv.lock"},
}


def _files(root: Path) -> dict[str, bytes]:
    """The files git would publish: tracked, or new and not ignored — the same
    list build.sh copies. A local tool cache in an app directory is not part
    of the app."""
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "."],
        capture_output=True, text=True, check=True,
    ).stdout
    return {name: (root / name).read_bytes() for name in listed.split("\0") if name and (root / name).is_file()}


@pytest.mark.parametrize("scenario", sorted(SCENARIO_BASE))
def test_a_scenario_app_differs_from_its_base_only_where_the_scenario_does(scenario):
    base, mine = _files(APPS / SCENARIO_BASE[scenario]), _files(APPS / scenario)
    shared = (set(base) | set(mine)) - SCENARIO_ONLY[scenario]
    drifted = sorted(f for f in shared if base.get(f) != mine.get(f))
    assert not drifted, f"apps/{scenario} has drifted from apps/{SCENARIO_BASE[scenario]}: {drifted}"


def test_the_pnpm_app_declares_what_the_npm_app_declares():
    base = json.loads((APPS / "ts-react" / "package.json").read_text(encoding="utf-8"))
    pnpm = json.loads((APPS / "ts-react-pnpm" / "package.json").read_text(encoding="utf-8"))
    for key in ("scripts", "dependencies", "devDependencies", "type", "private"):
        assert pnpm.get(key) == base.get(key), f"package.json {key} differs between the npm and pnpm apps"


def test_the_uv_app_declares_what_the_requirements_app_declares():
    requirements = {
        ln.strip() for ln in (APPS / "python-fastapi" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    }
    project = tomllib.loads((APPS / "python-uv" / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(project["project"]["dependencies"]) | set(project["dependency-groups"]["dev"])
    assert declared == requirements


def test_apps_carry_nothing_provisioning_generates():
    """App source is only what a tenant writes. Generated files here would mask
    the scaffold failing to produce them."""
    # .agent-rfc too: the scaffold creates it, and the security pack inside it
    # comes from the ONE shared security-pack/ — an app-local copy would be a
    # second pack to drift.
    generated = {
        ".github", "runtime", "fixtures", ".agents", ".cursorrules", "CLAUDE.md", "AGENTS.md",
        "GEMINI.md", ".agenticframework", "SCRATCH_TENANT.md", ".agent-history.log", ".agent-rfc",
    }
    apps = [p for p in APPS.iterdir() if p.is_dir()]
    # Every assertion below is inside the loop. `test_every_app_is_the_scenario_it_claims`
    # would catch an empty APPS, but a test that only holds because a sibling
    # holds stops holding the moment either is moved or skipped.
    assert len(apps) == len(SCENARIOS), f"expected {len(SCENARIOS)} apps, found {[a.name for a in apps]}"
    for app in apps:
        present = {p.name for p in app.iterdir()} & generated
        assert not present, f"apps/{app.name} contains generated paths: {present}"


def test_the_build_commits_as_the_author_it_checks_for_and_the_workflow_force_pushes():
    """build.sh commits the app and then the scaffold, through the tenant's own
    gate, on a fresh history; the workflow only pushes it (owner-approved force
    push, 2026-10-13 — the repository is pure output)."""
    build = BUILD.read_text(encoding="utf-8")
    assert f'WORKFLOW_AUTHOR="{BOT}"' in build and 'git config user.name "$WORKFLOW_AUTHOR"' in build
    assert "git checkout -q --orphan" in build
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build"]
    push = next(step["run"] for step in job["steps"] if step.get("name") == "Push")
    assert "git push -q --force origin main" in push and "commit" not in push.split("#")[0]


# ── Building for real, offline ───────────────────────────────────────────────


@pytest.fixture()
def install(tmp_path, monkeypatch):
    """~/.agent-framework as install-ai-stack.sh lays it out, minus the venv,
    and no machine-wide git hook: 3.0.0 arms none (vendoring-retired.md). The
    `agentsmith` a build runs is this checkout's (provider_shim, from
    conftest.py), so the tenant's gate is the one being changed.

    Still absent, deliberately: the venv install-ai-stack.sh builds. A caller that
    needs the gate to start an interpreter names one with AGENTSMITH_PYTHON, which
    is what the gate's own error message tells a real user to do."""
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    ignore = shutil.ignore_patterns("__pycache__", ".hitl_blobs")
    shutil.copytree(REPO / "scripts", fw / "scripts", ignore=ignore)
    shutil.copytree(REPO / "runtime", fw / "runtime", ignore=ignore)
    shutil.copytree(REPO / "fixtures" / "security", fw / "fixtures" / "security")
    for base in (REPO / "fixtures").glob("*_base.json"):
        shutil.copy(base, fw / "fixtures" / base.name)
    shutil.copytree(REPO / "workflow-templates", fw / "workflow-templates")
    shutil.copytree(REPO / ".githooks", fw / ".githooks")
    (fw / "templates").mkdir()
    for name in ("agent-rules.yaml", "governance.json", "architectures.yaml"):
        shutil.copy(REPO / "templates" / name, fw / "templates" / name)
    (fw / "docs").mkdir()
    for name in ("design-review-checklist.md", "validation-checklist.md", "review-levers.md"):
        shutil.copy(REPO / "docs" / name, fw / "docs" / name)
    # python3 with pyyaml for the rules render (a bare system python3 may lack
    # it), and a normal pycache location so a .pyc regression is visible.
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "python3").symlink_to(sys.executable)
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    monkeypatch.delenv("PYTHONPYCACHEPREFIX", raising=False)
    monkeypatch.delenv("SCRATCH_TENANTS_ALLOW_MANUAL_HEAD", raising=False)
    return home


REF = "0123456789abcdef0123456789abcdef01234567"
STACK_OF = {m["app"]: m["stack"] for m in _matrix()}


def _build(app: str, target: Path, build: Path = BUILD) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(build), app, str(target), STACK_OF[app], REF],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )


def _init(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(target)], check=True)


def _commit(target: Path, author: str) -> None:
    subprocess.run(["git", "-C", str(target), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "-c", f"user.name={author}", "-c", "user.email=a@x",
         "commit", "-q", "-m", "commit", "--no-verify"],
        check=True,
    )


# The test command each app's generated agent rules must carry (the lockfile
# decides the tool).
TEST_CMD = {
    "ts-react": "CI=true npm test", "ts-react-pnpm": "CI=true pnpm test", "go": "go test -race ./...",
    "python-fastapi": "pytest", "python-uv": "uv run pytest",
}


def _git_out(target: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True, check=True).stdout


@needs_git
@pytest.mark.parametrize(("app", "stack"), [(m["app"], m["stack"]) for m in _matrix()])
def test_each_app_builds_into_a_complete_tenant_offline(app, stack, install, tmp_path):
    target = tmp_path / "tenant"

    result = _build(app, target)

    assert result.returncode == 0, result.stdout + result.stderr
    # Two commits on a fresh history: the app, then the scaffold through the gate.
    assert _git_out(target, "log", "--format=%s").splitlines() == [
        f"chore: scaffold scratch-{app}", f"feat: the {app} app, before AgentSmith"]
    assert _git_out(target, "status", "--porcelain") == "", "everything init wrote is in the scaffold commit"
    # The app, verbatim.
    for rel, content in _files(APPS / app).items():
        assert (target / rel).read_bytes() == content, f"{rel} differs from the app source"
    # What the scaffold must have produced — asking the provider, holding none of it.
    workflows = target / ".github" / "workflows"
    for name in (f"ci-{stack}.yml", "agentsmith-gates.yml", "agentsmith-sync.yml", "eval-security.yml"):
        assert (workflows / name).is_file(), name
    assert f"setup-agentsmith@{REF}" in (workflows / "agentsmith-gates.yml").read_text(encoding="utf-8")
    assert not (target / ".github" / "actions").exists()
    assert not (target / "runtime").exists()
    assert not (target / "scripts" / "process_gate.py").exists()
    claude_md = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert re.search(r"## Test Command\n```\n(.*)\n```", claude_md).group(1) == TEST_CMD[app]
    assert (target / "SCRATCH_TENANT.md").is_file()
    assert not list(target.rglob("*.pyc"))
    for pack_file in (SCRATCH / "security-pack").iterdir():
        assert (target / ".agent-rfc" / "security" / pack_file.name).read_bytes() == pack_file.read_bytes()
    # The tenant's own gate over its history, as its CI runs it.
    gate = subprocess.run(["bash", ".githooks/process-gate", "ci", "--base", "0" * 40, "--head", "HEAD"],
                          cwd=target, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    assert gate.returncode == 0, gate.stdout + gate.stderr
    if stack == "python-fastapi":
        _the_ci_test_command_imports_an_app_beside_tests(workflows / f"ci-{stack}.yml", tmp_path / "layout")


def _the_ci_test_command_imports_an_app_beside_tests(workflow: Path, layout: Path) -> None:
    """The built tenant's own CI test command, run over the layout a FastAPI app
    has: a package `app/` beside `tests/`, and no pytest config. Until 3.0.0 the
    vendored framework tests put the repository root on the import path as a
    side effect, so a bare `pytest` passed and then failed in every tenant
    without them (vendoring-retired.md). A probe, not the scratch app's own
    tests, so the property needs nothing installed beyond pytest."""
    steps = [s for job in yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"].values()
             for s in job.get("steps", [])]
    [run] = [s["run"] for s in steps if s.get("name") == "Run tests"]
    [command] = [line.strip() for line in run.splitlines() if "pytest" in line and not line.strip().startswith("#")]
    argv = command.split()
    if argv[0] == "python":
        argv[0] = sys.executable
    try:
        import pytest_cov  # noqa: F401
    except ImportError:  # fail-open: coverage is CI's add-on, not what is under test here
        argv = [a for a in argv if not a.startswith("--cov")]
    (layout / "app").mkdir(parents=True)
    (layout / "app" / "__init__.py").write_text("READY = True\n")
    (layout / "tests").mkdir()
    (layout / "tests" / "test_probe.py").write_text("from app import READY\n\n\ndef test_the_app_imports():\n"
                                                    "    assert READY\n")
    done = subprocess.run([*argv, "-p", "no:cacheprovider"], cwd=layout, capture_output=True, text=True,
                          check=False, timeout=120)
    assert done.returncode == 0, f"`{command}` over app/ beside tests/:\n" + done.stdout[-2000:] + done.stderr[-2000:]


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
    assert "security-evidence" not in _git_out(target, "log", "--all", "--stat")


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
def test_the_build_fails_when_tenant_init_does(install, tmp_path):
    """A stack init does not know is init failing — and the build says so, rather
    than pushing a half-scaffolded tenant."""
    result = subprocess.run(["bash", str(BUILD), "go", str(tmp_path / "tenant"), "cobol", REF],
                            capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)

    assert result.returncode == 1
    assert "tenant init failed" in result.stdout + result.stderr


@needs_git
def test_the_build_copies_what_git_would_publish_not_local_junk(install, tmp_path):
    """`cp -R` carried an app directory's ignored node_modules/ or .ruff_cache/
    into a local build, so it differed from the workflow's clean checkout."""
    scratch = tmp_path / "scratch-tenants"
    shutil.copytree(SCRATCH, scratch)
    subprocess.run(["git", "init", "-q", "--template=", str(scratch)], check=True)
    (scratch / ".gitignore").write_text(".ruff_cache/\n")
    app = scratch / "apps" / "go"
    (app / ".ruff_cache").mkdir()
    (app / ".ruff_cache" / "junk").write_text("x")
    (app / "notes.txt").write_text("new, not ignored\n")

    target = tmp_path / "tenant"
    result = _build("go", target, build=scratch / "build.sh")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (target / ".ruff_cache").exists()
    assert (target / "notes.txt").read_text() == "new, not ignored\n"
    assert (target / "calc").is_dir(), "the app itself must still arrive"


# ── The adopted scratch tenant (.agent-rfc/designs/scratch-adopted.md) ───────

ADOPTED = SCRATCH / "adopted"


@needs_git
def test_adopt_sh_builds_a_tenant_whose_adoption_passed_its_own_gate(tmp_path):
    """The real `tenant adopt`, pinned to a ref; the adoption commit made through
    the tenant's contract-3 commit gate (the provider shim answers it); the
    tenant's own CI left as it was."""
    target, ref = tmp_path / "adopted", "0123456789abcdef0123456789abcdef01234567"

    done = subprocess.run(["bash", str(SCRATCH / "adopt.sh"), str(target), ref],
                          capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stdout + done.stderr
    log = subprocess.run(["git", "-C", str(target), "log", "--format=%s"], capture_output=True, text=True,
                         check=True).stdout.splitlines()
    assert log == ["chore: adopt AgentSmith gates", "feat: the ledger and its CI, before AgentSmith"]
    assert subprocess.run(["git", "-C", str(target), "status", "--porcelain"], capture_output=True, text=True,
                          check=True).stdout == "", "everything adopt wrote is in the adoption commit"
    setup = f"bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@{ref}"
    assert setup in (target / ".github/workflows/agentsmith-gates.yml").read_text(encoding="utf-8")
    assert json.loads((target / ".agenticframework/providers.json").read_text())["providers"]["gate"]["setup"] == setup
    assert (target / ".github/workflows/ci.yml").read_bytes() == (ADOPTED / ".github/workflows/ci.yml").read_bytes()
    assert subprocess.run(["git", "-C", str(target), "config", "--get", "core.hooksPath"], capture_output=True,
                          text=True, check=True).stdout.strip() == ".githooks", "the gates are armed"
    gate = subprocess.run(["bash", ".githooks/process-gate", "ci", "--base", "0" * 40, "--head", "HEAD"],
                          cwd=target, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    assert gate.returncode == 0, gate.stdout + gate.stderr


@needs_git
def test_adopt_sh_rebuilds_from_a_clean_history(tmp_path):
    """adopt refuses a repository already under the gates, so a second build
    must start over rather than fail on the first build's history."""
    target, ref = tmp_path / "adopted", "v0.0.0-test"
    for _ in range(2):
        done = subprocess.run(["bash", str(SCRATCH / "adopt.sh"), str(target), ref],
                              capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stdout + done.stderr
    count = subprocess.run(["git", "-C", str(target), "rev-list", "--count", "HEAD"], capture_output=True,
                           text=True, check=True).stdout.strip()
    assert count == "2"


def test_the_adopted_job_waits_on_both_of_the_tenants_workflows():
    """The tenant's own CI and the gates workflow adopt adds — named as each
    file names itself, or the wait would look for a run that never appears."""
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["adopted"]
    wait = next(s["run"] for s in job["steps"] if s.get("name", "").startswith("Wait"))
    own = yaml.safe_load((ADOPTED / ".github/workflows/ci.yml").read_text(encoding="utf-8"))["name"]
    gates = yaml.safe_load((REPO / "workflow-templates/agentsmith-gates.yml").read_text(encoding="utf-8"))["name"]
    assert f'"{own}"' in wait and f'"{gates}"' in wait
    assert any("adopt.sh" in s.get("run", "") and "$GITHUB_SHA" in s.get("run", "") for s in job["steps"]), \
        "the tenant must be pinned to the commit under test"
