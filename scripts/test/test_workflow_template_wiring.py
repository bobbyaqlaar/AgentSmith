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


def test_no_template_runs_agentsmith_from_a_copy() -> None:
    """Every template asks AgentSmith through the setup step the repository
    declares and the launcher — never a script, a runtime module or a composite
    action it would have to hold a copy of (vendoring-retired.md, 3.0.0).
    AgentSmith's own .github/workflows/eval-security.yml still runs the harness
    from its own checkout: that is the provider, not a tenant."""
    offenders = []
    for path in sorted(TEMPLATES.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for pattern in (r"python3? (-m )?scripts/", r"python3? -m runtime\.", r"uses:\s*\./\.github/actions/"):
            if re.search(pattern, text):
                offenders.append(f"{path.name}: {pattern}")
        if "process-gate" in text or "AgentSmith/.github/actions/" in text:
            assert "{{PROVIDER_SETUP}}" in text or path.name.startswith("agentsmith-"), \
                f"{path.name} asks the provider without installing it"
    assert not offenders, offenders
    security = (TEMPLATES / "eval-security.yml").read_text(encoding="utf-8")
    assert "bash .githooks/process-gate security check" in security


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


def test_every_stacks_ci_runs_the_security_port() -> None:
    """Go and TS tenants were never graded: only ci-python-fastapi.yml called
    eval-security.yml, though every stack is provisioned with it and none of
    its controls is Python-specific. The port has no non-strict mode."""
    import yaml

    stacks = sorted(TEMPLATES.glob("ci-*.yml"))
    # A glob with no floor: rename the templates and "every stack runs the strict
    # harness" passes over nothing (.agent-rfc/designs/sibling-sweep.md).
    assert len(stacks) >= 3, f"expected a ci-*.yml per stack, found {[p.name for p in stacks]}"
    for path in stacks:
        jobs = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]
        gate = jobs.get("security-checks", {})
        assert gate.get("uses") == "./.github/workflows/eval-security.yml", f"{path.name} skips the security port"
        assert "with" not in gate, f"{path.name} passes inputs eval-security.yml does not take"


# ── Governance steps block (G3) ──────────────────────────────────────────────


# A governance step that passes on failure is a rule nobody enforces: the CI run
# is green, the control did not hold, and only someone reading the log knows.
# Each entry says whether the step must block, and a non-blocking one must say
# in the file why it does not yet (`ambiguous-signals`).
GOVERNANCE_STEPS = {
    "RFC gate (Pillar 1)": True,
    # Blocking since G4 (2026-09-18), asked of the declared gate provider since
    # 3.0.0 (`kg check`): the committed graph against what the code maps to now.
    # A tenant with no graph yet passes with a warning inside that check.
    "Knowledge Graph is current (Pillar 2)": True,
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
