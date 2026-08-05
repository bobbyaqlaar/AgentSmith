"""
scripts/security/runners/_shared.py — the three ways a control runner borrows
an existing verifier, extracted so runners stay thin.

Every check the harness needs already exists somewhere: `verify_system.py` has
the `--check-*` family, `run-evals.py` owns fixture loading and thresholds, and
`runtime/test/` and `scripts/test/` hold suites that already assert the
behaviour a control claims. A runner's job is to point at one of those and
translate its outcome into a ControlResult — not to re-implement the check,
which would give the harness a second opinion that can drift from the one CI
enforces.

Both helpers below were inlined in a single runner each (`pii_postcall` shelled
out to verify_system, `adversarial_eval` loaded run-evals) and would have been
copied into a dozen more.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from security.registry import ControlSpec
from security.report import ControlResult


def _subprocess_result(
    control: ControlSpec, proc: subprocess.CompletedProcess, ok_msg: str, fail_msg: str
) -> ControlResult:
    if proc.returncode != 0:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=fail_msg,
            evidence={"stderr": (proc.stderr or proc.stdout)[:500]},
        )
    return ControlResult(control_id=control.id, status="pass", message=ok_msg, evidence={})


def verify_system(
    control: ControlSpec,
    ctx: dict[str, Any],
    flag: str,
    env: Optional[dict[str, str]] = None,
) -> ControlResult:
    """Delegate to `verify_system.py <flag>` — the health check CI already runs.

    ENVIRONMENT is forced to `staging` by default: several checks self-disable
    under `development`, so a control that ran in a developer shell would
    report Met while verifying nothing.
    """
    root = Path(ctx["root"])
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_system.py"), flag],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "ENVIRONMENT": "staging", **(env or {})},
    )
    return _subprocess_result(
        control, proc, f"verify_system {flag} passed", f"verify_system {flag} failed"
    )


# Settings that configure a TENANT's deployment and guardrail posture rather
# than framework code. The harness runs from the tenant's directory with its
# .env loaded and its CI-set modes exported, so a framework suite would inherit
# them: `MODERATION_HOOK=required` makes the gateway raise when no hook is
# declared, `BUDGET_BACKEND=postgres` points at a database that need not be
# running. Three budget tests failed that way and read as a compliance breach.
_TENANT_RUNTIME_KEYS = (
    "MODERATION_HOOK", "PROMPT_GUARD", "INPUT_GUARDRAIL", "TOOL_ALLOWLIST_STRICT",
    "TOOL_ALLOWLIST_PATH", "PROMPT_DENYLIST_PATH", "SECURITY_STRICT",
    "BUDGET_BACKEND", "IDEMPOTENCY_BACKEND", "DATABASE_URL",
    "AGENT_MONTHLY_USD_CAP", "TENANT_ID", "AI_STACK_MODE", "AGENT_MODEL_PROFILE",
)


def pytest_suite(
    control: ControlSpec,
    ctx: dict[str, Any],
    rel_path: str,
    env: Optional[dict[str, str]] = None,
    select: Optional[str] = None,
) -> ControlResult:
    """Delegate to an existing test module.

    Where a suite already asserts exactly what a control claims, running it is
    strictly better than writing a second check: one behaviour, one assertion,
    and the control cannot quietly disagree with the tests.

    Tenant deployment and guardrail settings are stripped first — see
    `_TENANT_RUNTIME_KEYS`. Without that, a framework suite runs under the
    tenant's posture and fails for reasons that have nothing to do with the
    control, turning a compliance check into an availability check. `env` lets
    a caller pin back whatever the suite genuinely needs; `select` passes a
    `-k` expression.
    """
    root = Path(ctx["root"])
    target = root / rel_path
    if not target.exists():
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"{rel_path} is missing — nothing verifies this control",
            evidence={},
        )
    clean = {k: v for k, v in os.environ.items() if k not in _TENANT_RUNTIME_KEYS}
    cmd = [sys.executable, "-m", "pytest", str(target), "-q"]
    if select:
        cmd += ["-k", select]
    proc = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        env={**clean, "ENVIRONMENT": "staging", **(env or {})},
    )
    return _subprocess_result(
        control, proc, f"{rel_path} passed", f"{rel_path} failed"
    )


def load_run_evals(root: Path):
    """Import `scripts/run-evals.py` as a module.

    Its filename has a hyphen, so it cannot be imported normally. Reusing it
    rather than re-reading fixture paths keeps the harness and the eval gate on
    one definition of where fixtures live, which suite falls back to which base
    file, and how a threshold resolves.
    """
    for extra in (str(root), str(root / "scripts")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    path = root / "scripts" / "run-evals.py"
    spec = importlib.util.spec_from_file_location("run_evals_harness", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def eval_suite_gateable(
    control: ControlSpec, ctx: dict[str, Any], suite: str, minimum: int = 3
) -> ControlResult:
    """A judge-backed eval gate exists, has enough cases to gate, and resolves
    a threshold.

    Deliberately does NOT run the judge. A security control that needs a
    provider credential and a quota would report Gap whenever an account is
    unfunded — turning a compliance check into an availability check, and
    exactly the confusion the eval gates themselves had to be fixed for. The
    verifiable claim is that the gate is wired and would bite; whether quality
    passes is what CI's eval steps report.
    """
    root = Path(ctx["root"])
    revals = load_run_evals(root)
    cases = revals._load_cases(suite)
    if len(cases) < minimum:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"{suite}: {len(cases)} case(s), need ≥{minimum} to gate",
            evidence={"cases": str(len(cases))},
        )
    threshold = revals._resolve_fail_below(suite, None)
    return ControlResult(
        control_id=control.id,
        status="pass",
        message=f"{suite}: {len(cases)} cases, threshold {threshold:.2f}",
        evidence={"cases": str(len(cases)), "threshold": f"{threshold:.2f}"},
    )
