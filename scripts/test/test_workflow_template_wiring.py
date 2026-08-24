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
"""

from __future__ import annotations

import re
from pathlib import Path

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
