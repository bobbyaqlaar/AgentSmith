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
