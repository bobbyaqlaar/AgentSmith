"""
scripts/test/test_workflow_template_wiring.py — guards on the two places
workflow YAML is duplicated on purpose.

Both duplications are legitimate, which is exactly why they need a test rather
than a cleanup: GitHub resolves `uses: ./.github/workflows/<name>` inside the
CALLING repo, so a reusable workflow the framework calls in its own self-test
must also exist as a file in every tenant that calls it. Nothing enforced the
copies staying in step, and nothing enforced the copies shipping at all — a
callee missing from runtime/cli.py's WORKFLOWS list makes GitHub reject
the whole tenant CI workflow as invalid, which is how eval-security.yml went
out broken for every Python/FastAPI tenant.

A THIRD list duplicates the same information: hooks/post-checkout's own
`for wf in ...` bash array — the actual provisioning path for a `git checkout`
after opt-in, entirely separate from `agentsmith tenant init` /
runtime/cli.py's WORKFLOWS. The comment above used to say that loop was
"gone" after the scaffold moved into runtime/cli.py — it wasn't; it is a
second, independent implementation of the same copy step, and it went stale
the same way WORKFLOWS almost did: eval-security.yml was added to WORKFLOWS
and to ci-python-fastapi.yml's job list without being added to this bash
array too, found onboarding AqlaarTeleologyStudio (its `ci-python-fastapi.yml`
was rejected by GitHub outright). test_hooks_workflow_array_matches_cli_
workflows below pins the two lists against each other so neither can drift
ahead of the other silently again.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "workflow-templates"
INSTALLER = REPO / "install-ai-stack.sh"
HOOK = REPO / "hooks" / "post-checkout"

_USES = re.compile(r"uses:\s*\./\.github/workflows/([\w.-]+)")


def _referenced_callees() -> set[str]:
    names: set[str] = set()
    for template in TEMPLATES.glob("*.yml"):
        names |= set(_USES.findall(template.read_text(encoding="utf-8")))
    return names


def _provisioned_workflows() -> set[str]:
    """The list `agentsmith tenant init` actually copies.

    This used to scrape the `for wf in ...` loop out of install-ai-stack.sh.
    That loop is gone: the scaffold moved into runtime/cli.py, where it is a
    value a test can import rather than shell text a test has to parse. Reading
    the real list also means this can no longer pass because a regex matched
    something that is no longer executed.
    """
    import sys as _sys

    _sys.path.insert(0, str(REPO))
    from runtime.cli import WORKFLOWS, STACKS

    return set(WORKFLOWS) | {f"ci-{stack}.yml" for stack in STACKS}


def test_every_referenced_callee_exists_as_a_template() -> None:
    missing = {n for n in _referenced_callees() if not (TEMPLATES / n).exists()}
    assert not missing, f"ci-*.yml references workflow-templates that don't exist: {missing}"


def test_every_referenced_callee_is_provisioned_into_tenants() -> None:
    """A caller without its callee is not a degraded workflow — GitHub refuses
    to run the file at all."""
    provisioned = _provisioned_workflows()
    missing = {n for n in _referenced_callees() if n not in provisioned}
    assert not missing, (
        f"referenced by a ci-*.yml template but never copied into tenant repos "
        f"by `agentsmith tenant init` (runtime/cli.py WORKFLOWS): {missing}"
    )


def _hook_workflow_array() -> set[str]:
    """The static part of hooks/post-checkout's `for wf in ...` array —
    excludes `$WF_CI` (the per-stack file, a shell variable, handled
    separately in both this hook and runtime/cli.py) so what remains is
    directly comparable to runtime.cli.WORKFLOWS."""
    text = HOOK.read_text(encoding="utf-8")
    m = re.search(r"for wf in (.+?); do", text, re.DOTALL)
    assert m, "hooks/post-checkout's `for wf in ...` loop not found — has it moved or been renamed?"
    names = set(re.findall(r'"([\w.-]+\.yml)"', m.group(1)))
    names.discard("$WF_CI")
    return names


def test_hooks_workflow_array_matches_cli_workflows() -> None:
    """hooks/post-checkout (fires on `git checkout` after opt-in) and
    runtime/cli.py's WORKFLOWS (what `agentsmith tenant init` copies) are two
    independent implementations of the same provisioning step. Nothing keeps
    them in step by construction — this is that check."""
    import sys as _sys

    _sys.path.insert(0, str(REPO))
    from runtime.cli import WORKFLOWS

    hook_only = _hook_workflow_array() - set(WORKFLOWS)
    cli_only = set(WORKFLOWS) - _hook_workflow_array()
    assert not hook_only, f"hooks/post-checkout copies these but runtime/cli.py's WORKFLOWS doesn't: {hook_only}"
    assert not cli_only, f"runtime/cli.py's WORKFLOWS copies these but hooks/post-checkout doesn't: {cli_only}"


def test_reusable_security_workflow_matches_its_tenant_template() -> None:
    """The framework's self-test calls its own copy; a tenant's CI calls the
    copy provisioned into the tenant. Same workflow, two homes, no sync
    mechanism — so assert they haven't drifted."""
    framework = (REPO / ".github" / "workflows" / "eval-security.yml").read_text(
        encoding="utf-8"
    )
    template = (TEMPLATES / "eval-security.yml").read_text(encoding="utf-8")
    assert framework == template, (
        ".github/workflows/eval-security.yml and workflow-templates/eval-security.yml "
        "have diverged — edit both, or the framework self-test and tenant CI stop "
        "running the same security harness"
    )


def test_stack_agnostic_templates_do_not_cache_pip_on_tenant_manifests() -> None:
    """`setup-python` with `cache: pip` and no `cache-dependency-path` globs
    for **/requirements.txt|pyproject.toml and FAILS the step when neither
    exists. Every template except ci-python-fastapi.yml runs in Go and TS
    tenants too, which have neither — found onboarding scratch ts-react and go
    tenants, where every eval job and both CD jobs died at "Setup Python"."""
    offenders = []
    for path in sorted(TEMPLATES.glob("*.yml")):
        if path.name == "ci-python-fastapi.yml":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r'cache:\s*"?pip"?', text) and "cache-dependency-path:" not in text:
            offenders.append(path.name)
    assert not offenders, (
        f"these templates cache pip without cache-dependency-path, which fails on a "
        f"tenant with no requirements.txt/pyproject.toml: {offenders}"
    )


def test_security_workflow_installs_the_runtimes_core_dependencies() -> None:
    """eval-security.yml delegates controls to runtime/test/ suites, which import
    the runtime — so it must install what the runtime itself requires. It
    didn't: SEC-BUDGET-001 failed in AqlaarTeleologyStudio on `No module named
    'httpx'`, a missing dependency reported as a control violation."""
    import tomllib

    deps = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    names = {re.split(r"[<>=!~\[ ]", d, maxsplit=1)[0].lower() for d in deps}
    installs = " ".join(
        ln for ln in (TEMPLATES / "eval-security.yml").read_text(encoding="utf-8").splitlines()
        if "pip install" in ln
    ).lower()
    missing = {n for n in names if not re.search(rf'(^|[\s"]){re.escape(n)}([<>=\s"]|$)', installs)}
    assert not missing, f"eval-security.yml does not install runtime core deps: {missing}"


def test_vendored_runtime_tests_are_exactly_what_the_security_harness_runs() -> None:
    """runtime/test/ is vendored only as far as scripts/security's pytest_suite()
    bindings need (plus their conftest.py). Too few and a SEC control fails on a
    missing suite; too many and a tenant's `pytest` collects framework-internal
    tests (36 failures in a scratch python-fastapi tenant). Both vendoring
    paths carry the list, so both are pinned to the bindings."""
    bound = set()
    for runner in (REPO / "scripts" / "security" / "runners").glob("*.py"):
        bound |= set(re.findall(r'"runtime/test/(test_\w+\.py)"', runner.read_text(encoding="utf-8")))
    assert bound, "no pytest_suite bindings found — has the harness moved?"
    expected = bound | {"conftest.py"}

    hook = re.search(r"^TENANT_RUNTIME_TESTS=\(([^)]*)\)", HOOK.read_text(encoding="utf-8"), re.M)
    upgrade_src = (REPO / "runtime" / "machine" / "upgrade.py").read_text(encoding="utf-8")
    upgrade = re.search(r"^TENANT_RUNTIME_TESTS = \((.*?)\)", upgrade_src, re.S | re.M)
    assert hook and upgrade
    assert set(hook.group(1).split()) == expected, "hooks/post-checkout TENANT_RUNTIME_TESTS"
    assert set(re.findall(r'"([\w.]+)"', upgrade.group(1))) == expected, "agentsmith upgrade TENANT_RUNTIME_TESTS"


def test_python_template_pins_ruff_to_the_frameworks_own_version() -> None:
    """An unpinned linter is a gate that changes without a commit."""
    pin = re.search(r"^ruff==([\d.]+)", (REPO / "requirements-lint.txt").read_text(encoding="utf-8"), re.M)
    assert pin, "requirements-lint.txt no longer pins ruff"
    template = (TEMPLATES / "ci-python-fastapi.yml").read_text(encoding="utf-8")
    assert f'"ruff=={pin.group(1)}"' in template


def test_cd_deploys_only_what_ci_passed() -> None:
    """cd-staging/cd-production ran `on: push` in parallel with CI and nothing
    made them wait — AqlaarTeleologyStudio's production deploy went green on
    commits whose CI was red. They must trigger on the stack CI completing,
    proceed only on success, deploy the commit CI ran against, and name every
    stack's CI workflow exactly (a renamed CI silently disconnects CD)."""
    import yaml

    ci_names = {
        yaml.safe_load(p.read_text(encoding="utf-8"))["name"] for p in TEMPLATES.glob("ci-*.yml")
    }
    for env, branch in (("staging", "develop"), ("production", "main")):
        doc = yaml.safe_load((TEMPLATES / f"cd-{env}.yml").read_text(encoding="utf-8"))
        on = doc.get("on", doc.get(True))  # PyYAML 1.1 reads a bare `on` key as True
        assert set(on) == {"workflow_run"}, f"cd-{env}.yml must not also trigger on {set(on) - {'workflow_run'}}"
        run = on["workflow_run"]
        assert set(run["workflows"]) == ci_names, f"cd-{env}.yml waits on {run['workflows']}, CI is named {ci_names}"
        assert run["branches"] == [branch] and run["types"] == ["completed"]
        job = doc["jobs"]["deploy"]
        assert "workflow_run.conclusion == 'success'" in job["if"]
        checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
        assert checkout["with"]["ref"] == "${{ github.event.workflow_run.head_sha }}"
    for path in TEMPLATES.glob("ci-*.yml"):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        on = doc.get("on", doc.get(True))
        assert {"main", "develop"} <= set(on["push"]["branches"]), f"{path.name}: staging CD needs CI on develop"


def test_ts_react_template_assumes_no_particular_test_runner_or_script_names() -> None:
    """A stock `create-vite` react-ts scaffold defines neither a `tsc` script
    nor Jest: `npm run tsc` failed with `Missing script`, and Vitest rejects
    `--watchAll`. The template may call only scripts every npm project has, or
    guard the rest with `--if-present` / an explicit existence check."""
    text = (TEMPLATES / "ci-ts-react.yml").read_text(encoding="utf-8")
    runs = [ln.strip() for ln in text.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(runs)
    assert "npm run tsc" not in body
    for jest_only in ("--watchAll", "--ci"):
        assert jest_only not in body, f"{jest_only} is a Jest-only flag; Vitest exits on it"


def test_hook_actually_writes_every_callee_into_a_fresh_tenant(tmp_path, monkeypatch):
    """End to end, against the real hook — this is the test that would have
    caught AqlaarTeleologyStudio's broken ci-python-fastapi.yml: a scratch
    repo whose detected stack is python-fastapi ends up with EVERY workflow
    ci-python-fastapi.yml references as a callee, not just the ones some
    earlier version of the copy list happened to include."""
    import shutil as _shutil

    if _shutil.which("git") is None or _shutil.which("bash") is None:
        import pytest as _pytest
        _pytest.skip("git and bash required")

    home = tmp_path / "home"
    fw = home / ".agent-framework"
    _shutil.copytree(TEMPLATES, fw / "workflow-templates")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DISABLE_AI_STACK", raising=False)

    work = tmp_path / "repo"
    work.mkdir()
    subprocess_run = __import__("subprocess").run
    subprocess_run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    (work / "requirements.txt").write_text("fastapi\n")
    (work / ".agenticframework").mkdir()
    (work / ".agenticframework" / "enabled").touch()

    result = subprocess_run(
        ["bash", str(HOOK)], cwd=work, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    written = {p.name for p in (work / ".github" / "workflows").glob("*.yml")}
    referenced = {
        n for n in _USES.findall(
            (work / ".github" / "workflows" / "ci-python-fastapi.yml").read_text(encoding="utf-8")
        )
    }
    missing = referenced - written
    assert not missing, f"ci-python-fastapi.yml references callees never written into the tenant: {missing}"


def test_every_stacks_ci_runs_the_strict_security_harness() -> None:
    """Go and TS tenants were never graded: only ci-python-fastapi.yml called
    eval-security.yml, though every stack is provisioned with it and none of
    its controls is Python-specific."""
    import yaml

    for path in sorted(TEMPLATES.glob("ci-*.yml")):
        jobs = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]
        gate = jobs.get("security-checks", {})
        assert gate.get("uses") == "./.github/workflows/eval-security.yml", f"{path.name} skips the security harness"
        assert gate.get("with", {}).get("strict") is True, f"{path.name} runs the security harness non-strict"


# ── Governance steps block (G3) ──────────────────────────────────────────────


# A governance step that passes on failure is a rule nobody enforces: the CI run
# is green, the control did not hold, and only someone reading the log knows.
# Each entry says whether the step must block, and a non-blocking one must say
# in the file why it does not yet (`ambiguous-signals`).
GOVERNANCE_STEPS = {
    "RFC gate (Pillar 1)": True,
    "IDE config drift check (Pillar 6/7)": True,
    # Blocking since G4 (2026-09-18). It runs `verify_system.py --check-kg`, the
    # same check the framework runs on itself: the inline version it replaced
    # rebuilt the graph and then counted nodes in the COMMITTED file without
    # ever comparing them, so a stale graph passed every run. A tenant with no
    # graph at all still passes with a warning inside that check, until
    # `agentsmith tenant init` provisions one (G7).
    "Validate Knowledge Graph (Pillar 2)": True,
    # Not a gate: it reports on Phoenix and the model registry, which a tenant
    # may legitimately not have configured in CI.
    "Framework health check (Pillar 3/5)": False,
}
CI_TEMPLATES = ("ci-python-fastapi", "ci-go", "ci-ts-react")


@pytest.mark.parametrize("template", CI_TEMPLATES)
def test_governance_steps_block_on_failure(template) -> None:
    doc = yaml.safe_load((REPO / "workflow-templates" / f"{template}.yml").read_text(encoding="utf-8"))
    seen = {}
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            name = step.get("name", "")
            if name in GOVERNANCE_STEPS:
                seen[name] = step
    assert set(seen) == set(GOVERNANCE_STEPS), f"{template}: governance steps renamed or removed: {sorted(seen)}"
    for name, step in seen.items():
        blocks = GOVERNANCE_STEPS[name]
        passes_on_failure = bool(step.get("continue-on-error")) or "|| true" in (step.get("run") or "")
        assert passes_on_failure is not blocks, (
            f"{template}: step {name!r} "
            + ("passes on failure — a governance gate that cannot fail is not a gate"
               if blocks else "is expected to be non-blocking; if that changed, update this test with the reason")
        )


# ── The provider checkout works whether or not AgentSmith is private ─────────
#
# .agent-rfc/designs/governance-providers.md decision 4 promised that going
# public "removes a step without changing a tenant". It was recorded and never
# implemented: both templates passed `token: ${{ secrets.AGENTSMITH_READ_TOKEN }}`
# outright, and an unset secret renders as the EMPTY STRING — which replaces the
# run's default token rather than falling back to it. So a tenant that dropped a
# secret it no longer needed would have got a broken checkout on the day the
# provider went public (.agent-rfc/designs/public-provider-checkout.md).

_PROVIDER_TEMPLATES = ("agentsmith-gates.yml", "agentsmith-sync.yml")


@pytest.mark.parametrize("name", _PROVIDER_TEMPLATES)
def test_the_provider_checkout_falls_back_to_the_runs_own_token(name: str) -> None:
    """Every use of the secret offers `github.token` when it is unset."""
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    bare = [
        (n, line.strip())
        for n, line in enumerate(text.splitlines(), 1)
        if "secrets.AGENTSMITH_READ_TOKEN" in line
        and not line.strip().startswith("#")
        and "github.token" not in line
    ]
    assert not bare, (
        f"{name} requires AGENTSMITH_READ_TOKEN outright at {bare} — a public provider needs no "
        "secret, and an unset one is the empty string, not a fallback. Use "
        "`${{ secrets.AGENTSMITH_READ_TOKEN || github.token }}`"
    )


@pytest.mark.parametrize("name", _PROVIDER_TEMPLATES)
def test_a_template_does_not_state_the_provider_is_private(name: str) -> None:
    """The comment said "AgentSmith is private" as a fact about the world. A
    file that dates itself to a visibility goes stale the day it changes; what
    does not change is what the secret is FOR."""
    text = (TEMPLATES / name).read_text(encoding="utf-8").lower()
    assert "agentsmith is private" not in text, (
        f"{name} states the provider's visibility as a fact — say what the secret is for instead"
    )
