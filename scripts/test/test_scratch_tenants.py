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
    the hook failing to produce them."""
    # .agent-rfc too: the hook creates it, and the security pack inside it
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


def test_the_commit_step_disarms_hooks_and_uses_the_author_build_sh_expects():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git -c core.hooksPath=/dev/null commit" in text
    assert f'git config user.name  "{BOT}"' in text
    assert f'WORKFLOW_AUTHOR="{BOT}"' in BUILD.read_text(encoding="utf-8")


# ── Building for real, offline ───────────────────────────────────────────────


@pytest.fixture()
def install(tmp_path, monkeypatch):
    """~/.agent-framework and ~/.git_templates as install-ai-stack.sh lays them out,
    minus the venv. Completeness matters: build.sh fails on ANY hook warning, and
    every omission here has hidden a defect. This fixture claimed to be complete
    while copying one of three files in templates/, none of three in docs/, and one
    of four machine hooks — so no test using it could reach a commit through the
    process gate, or see the pre-commit guardrails run at all
    (.agent-rfc/designs/first-commit-guardrail.md).

    Still absent, deliberately: the venv install-ai-stack.sh builds. A caller that
    needs the gate to start an interpreter names one with AGENTSMITH_PYTHON, which
    is what the gate's own error message tells a real user to do."""
    home = tmp_path / "home"
    fw = home / ".agent-framework"
    ignore = shutil.ignore_patterns("__pycache__", ".hitl_blobs")
    shutil.copytree(REPO / "scripts", fw / "scripts", ignore=ignore)
    shutil.copytree(REPO / "runtime", fw / "runtime", ignore=ignore)
    shutil.copytree(REPO / "fixtures" / "security", fw / "fixtures" / "security")
    shutil.copytree(REPO / "fixtures" / "security" / "templates", fw / "shared" / "security")
    for base in (REPO / "fixtures").glob("*_base.json"):
        shutil.copy(base, fw / "fixtures" / base.name)
    shutil.copytree(REPO / "workflow-templates", fw / "workflow-templates")
    shutil.copytree(REPO / ".github" / "actions", fw / "github-actions")
    (fw / "templates").mkdir()
    # All three the installer copies, not just the rules: governance.json is the
    # registry the process gate reads (it runs without pyyaml) and
    # architectures.yaml is what --architecture renders. The docstring above
    # promised "as install-ai-stack.sh lays them out" while copying one of the
    # three, so no test using this fixture could reach a commit through the gate
    # (.agent-rfc/designs/first-commit-guardrail.md).
    for name in ("agent-rules.yaml", "governance.json", "architectures.yaml"):
        shutil.copy(REPO / "templates" / name, fw / "templates" / name)
    # The three docs the installer copies too. review-levers.md is not optional
    # reading material here: the process gate validates that a design's
    # `## Levers` cites a real lever, and without this file it blocks the
    # scaffold's own commit on a machine that has no checkout.
    (fw / "docs").mkdir()
    for name in ("design-review-checklist.md", "validation-checklist.md", "review-levers.md"):
        shutil.copy(REPO / "docs" / name, fw / "docs" / name)
    # All four machine hooks the installer places here, not just post-checkout.
    # pre-commit is the one that carries the bare-except and AI-marker guardrails,
    # so a fixture without it cannot see a commit refused by them — which is how a
    # tenant's first commit stayed broken while these tests were green
    # (.agent-rfc/designs/first-commit-guardrail.md).
    hooks = home / ".git_templates" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("pre-commit", "commit-msg", "post-commit", "post-checkout"):
        shutil.copy(REPO / "hooks" / name, hooks / name)
    # post-commit auto-tags and pushes. These repos have no remote, so a push
    # cannot reach anything, but saying so beats relying on it.
    monkeypatch.setenv("AGENTSMITH_AUTOPUSH", "0")
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


def _build(app: str, target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(BUILD), app, str(target)],
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


# How the hook names each stack, and the test command each app's generated
# agent rules must carry (the lockfile decides the tool).
STACK_LABEL = {"ts-react": "TS_REACT", "go": "GO", "python-fastapi": "PYTHON_FASTAPI"}
TEST_CMD = {
    "ts-react": "CI=true npm test", "ts-react-pnpm": "CI=true pnpm test", "go": "go test -race ./...",
    "python-fastapi": "pytest", "python-uv": "uv run pytest",
}


@needs_git
@pytest.mark.parametrize(("app", "stack"), [(m["app"], m["stack"]) for m in _matrix()])
def test_each_app_builds_into_a_complete_tenant_offline(app, stack, install, tmp_path):
    target = tmp_path / "tenant"

    result = _build(app, target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Detected stack [{STACK_LABEL[stack]}]" in result.stdout
    # The app, verbatim.
    for rel, content in _files(APPS / app).items():
        assert (target / rel).read_bytes() == content, f"{rel} differs from the app source"
    # What provisioning must have produced.
    assert (target / ".github" / "workflows" / f"ci-{stack}.yml").is_file()
    assert (target / ".github" / "actions" / "gcp-auth" / "action.yml").is_file()
    assert (target / "scripts" / "run-security-checks.py").is_file()
    assert sorted(p.name for p in (target / "runtime" / "test").iterdir()) == sorted([
        "conftest.py", "test_hitl_gate.py", "test_dead_letter.py",
        "test_llm_gateway_budget.py", "test_self_correction.py",
    ])
    claude_md = (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert re.search(r"## Test Command\n```\n(.*)\n```", claude_md).group(1) == TEST_CMD[app]
    assert (target / "SCRATCH_TENANT.md").is_file()
    assert not list(target.rglob("*.pyc"))
    for pack_file in (SCRATCH / "security-pack").iterdir():
        assert (target / ".agent-rfc" / "security" / pack_file.name).read_bytes() == pack_file.read_bytes()
    # The harness's own verdict, not a re-derivation of "is this a placeholder":
    # strict, with the moderation default eval-security.yml sets, and without
    # the framework's own job environment — Self-Test sets DATABASE_URL and a
    # postgres idempotency backend that a tenant's security job does not have.
    harness = subprocess.run(
        [sys.executable, "scripts/run-security-checks.py", "--mode", "ci", "--strict"],
        cwd=target, capture_output=True, text=True, check=False,
        env={"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "MODERATION_HOOK": "optional"},
    )
    assert harness.returncode == 0, harness.stdout + harness.stderr
    if (target / "pyproject.toml").is_file():
        # The project's own ruff settings must still reach the vendored code.
        assert 'extend = "../pyproject.toml"' in (target / "runtime" / "ruff.toml").read_text(encoding="utf-8")


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
@pytest.mark.parametrize("missing", ["runtime", "shared/security"])
def test_the_build_fails_when_the_install_cannot_provision(install, tmp_path, missing):
    """shared/security used to be skipped without a word, leaving the pack
    half-seeded and the harness failing on files nobody said were missing."""
    shutil.rmtree(install / ".agent-framework" / missing)

    result = _build("python-fastapi", tmp_path / "tenant")

    assert result.returncode == 1
    assert "could not fully provision" in result.stdout


@needs_git
def test_the_build_fails_if_the_hook_rewrites_gitignore(install, tmp_path, monkeypatch):
    """The guard has to be able to fail. build.sh declares
    AGENTSMITH_TENANT_VISIBILITY=private so these public fixture repos still
    track the IDE config files a real private tenant tracks; this proves the
    build STOPS when a hook ignores that declaration, rather than publishing a
    tenant that silently differs from the ones it stands in for.

    The stimulus is a stale installed hook — one predating the override, which
    is the realistic way this happens, since the machine install lags the
    checkout. Simulated by renaming the variable the installed hook reads, so
    build.sh's export reaches a hook that does not honour it.

    For the go app, which has no .gitignore, the hook CREATES one — the first
    version of this check only compared existing files and missed it.
    """
    installed = install / ".git_templates" / "hooks" / "post-checkout"
    text = installed.read_text()
    assert "AGENTSMITH_TENANT_VISIBILITY" in text, "the installed hook should read the override"
    installed.write_text(text.replace("AGENTSMITH_TENANT_VISIBILITY", "AGENTSMITH_TENANT_VISIBILITY_OLD"))

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
    assert "AGENTSMITH_TENANT_VISIBILITY" in result.stdout + result.stderr, \
        "the error has to name the cause, not send the reader to their gh auth"


@needs_git
def test_the_build_keeps_ide_configs_tracked_on_a_public_fixture(install, tmp_path, monkeypatch):
    """The other half: with a current hook and a gh that reports PUBLIC — which
    these five fixture repos genuinely are since 2026-09-27 — the build still
    succeeds and leaves the IDE config files tracked."""
    target = tmp_path / "tenant"
    _init(target)
    subprocess.run(
        ["git", "-C", str(target), "remote", "add", "origin", "https://github.com/example/scratch.git"], check=True
    )
    public = tmp_path / "publicgh"
    public.mkdir()
    (public / "gh").write_text('#!/bin/sh\necho PUBLIC\n')
    (public / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{public}{os.pathsep}{os.environ['PATH']}")

    result = _build("go", target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (target / ".gitignore").exists(), "the declaration must keep the fixture faithful"


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
    result = subprocess.run(
        ["bash", str(scratch / "build.sh"), "go", str(target)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (target / ".ruff_cache").exists()
    assert (target / "notes.txt").read_text() == "new, not ignored\n"
    assert (target / "calc").is_dir(), "the app itself must still arrive"
