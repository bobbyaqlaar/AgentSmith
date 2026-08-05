"""
scripts/security/runners/delegating.py — controls whose verification already
exists elsewhere in the repo.

These were the largest category of `runner … not implemented`: 14 of 23
controls skipped, and `skip` counts as green even under `--strict`, so the
harness reported success for a control surface it had never examined.
`SEC-HITL-001` — mandatory human review — was among them, while a live run
showed that gate failing open on a sanctions hit.

Each runner here is a few lines because the check it needs is already written
and already enforced by CI. Adding a second implementation would create a
control that can disagree with the tests, which is worse than no control: it
would eventually report Met while the behaviour regressed.

One module rather than one file per control, deliberately. These are bindings,
not logic; splitting them would make the harness look substantial while saying
the same thing.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult
from security.runners._shared import (
    eval_suite_gateable,
    failed,
    pytest_suite,
    verify_system,
)


# ── Delegating straight to an existing suite or health check ─────────────────


def hitl_gate(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    """SEC-HITL-001 — `runtime/test/test_hitl_gate.py` already asserts that the
    gate cannot be skipped, that a caller must supply exactly one of
    `gate_activity_name`/`gate_result`, and that a timeout dead-letters rather
    than approving. It runs without Temporal or Postgres, so it is a usable
    control check rather than an integration test."""
    return pytest_suite(control, ctx, "runtime/test/test_hitl_gate.py")


# SEC-DLQ-001 is deliberately NOT bound here. `verify_system --check-dlq` is a
# reachability probe ("DLQ reachable — DATABASE_URL"), so binding it would make
# the control fail whenever Postgres is down — an availability check wearing a
# compliance label, which is the confusion this whole phase exists to remove.
# The dead-letter ENVELOPE is asserted by runtime/test/test_hitl_gate.py, but
# that suite is already SEC-HITL-001's evidence and one suite reported as two
# green controls inflates the harness rather than strengthening it. Needs a
# dedicated infra-free dead_letter suite first.


def self_correction(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    """SEC-SELF-001 — the recoverable-step / self-correction wrappers are
    asserted by the workflow-template suite."""
    return pytest_suite(control, ctx, "scripts/test/test_workflow_template_wiring.py")


def budget_caps(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    """SEC-BUDGET-001 — budget reservation and the degrade ladder on breach.

    Backends pinned to in-process: the control verifies that a breach degrades
    and ultimately halts, which is code behaviour. Left to inherit the tenant
    .env it picked up `BUDGET_BACKEND=postgres` against a database that was not
    running and reported a control failure for an unrelated reason.
    """
    return pytest_suite(
        control, ctx, "runtime/test/test_llm_gateway_budget.py",
        env={"BUDGET_BACKEND": "memory", "IDEMPOTENCY_BACKEND": "memory"},
    )


def change_gates(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    """SEC-CHANGE-001 — the hooks that enforce RFC/commit discipline."""
    return verify_system(control, ctx, "--check-hooks")


# ── Eval gates: wired and gateable, without running a judge ──────────────────


def eval_golden(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    return eval_suite_gateable(control, ctx, "golden")


def eval_fairness(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    return eval_suite_gateable(control, ctx, "fairness")


def eval_hallucination(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    return eval_suite_gateable(control, ctx, "hallucination")


# ── Tenant-declared controls ─────────────────────────────────────────────────


def tenant_suite(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    """A control the TENANT declares, evidenced by a test suite in its own repo.

    The framework registry cannot enumerate every domain control a tenant needs
    — KYC Sentinel's evidence-mandated rating floor (a sanctions hit forces
    human review whatever the model rated) is a real control with tests and
    documentation that the compliance surface simply could not see.

    Deliberately runs the tenant's own suite rather than importing a declared
    callable: the tests already encode what the control claims, including its
    negative cases, and a second assertion written here could drift from them.
    Tenant registries are additive-only (see load_control_registry), so this
    cannot be used to weaken a framework control.
    """
    if not control.suite:
        return failed(control, "tenant control declares no `suite` to run")
    return pytest_suite(control, ctx, control.suite, base=Path(ctx["tenant_root"]))


# ── Static: the gateway is the only provider path for workload calls ─────────

# Provider SDKs and the eval-path router. runtime/llm_gateway.py's own
# docstring states the rule this enforces: "Workers MUST NOT import
# cost_router.py directly."
_FORBIDDEN_IN_WORKLOAD = {
    "anthropic", "openai", "groq", "cohere", "mistralai",
    "google.generativeai", "boto3", "cost_router",
}
# Where a tenant's workload code lives. Tests and scripts are exempt: the eval
# harness legitimately uses cost_router, and test doubles import SDKs.
_WORKLOAD_DIRS = ("agents", "workflows", "runtime/workflows")


def gateway_static(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    """SEC-GW-001 — workload code reaches models through the gateway only.

    The map row has always described this as "Static: tenant activities import
    gateway, not raw provider"; nothing performed it. A direct SDK import
    bypasses budget reservation, the degrade ladder, redaction, prompt guard
    and the moderation hook in one step — every gateway control at once — and
    it is invisible at runtime because the call simply succeeds.
    """
    root = Path(ctx["root"])
    offenders: list[str] = []
    for rel in _WORKLOAD_DIRS:
        base = root / rel
        if not base.is_dir():
            continue
        for py in base.rglob("*.py"):
            if "test" in py.parts or py.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    root_pkg = name.split(".")[0]
                    if name in _FORBIDDEN_IN_WORKLOAD or root_pkg in _FORBIDDEN_IN_WORKLOAD:
                        offenders.append(f"{py.relative_to(root)}: {name}")

    if offenders:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"{len(offenders)} workload import(s) bypass the gateway",
            evidence={"offenders": "; ".join(sorted(set(offenders))[:5])},
        )
    scanned = [d for d in _WORKLOAD_DIRS if (root / d).is_dir()]
    return ControlResult(
        control_id=control.id,
        status="pass",
        message=f"no direct provider imports in {', '.join(scanned) or '(no workload dirs)'}",
        evidence={"dirs": ",".join(scanned)},
    )
