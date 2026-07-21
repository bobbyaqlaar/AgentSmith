"""run-security-checks.py — unified security harness for AgentSmith tenant apps."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from security.registry import load_control_registry
from security.report import ControlResult, write_evidence_pack
from security.runners import RUNNERS

Mode = Literal["smoke", "ci", "full"]


def _install_root() -> Path:
    """Root of the checkout this script lives in (file-relative).

    Renamed from `_repo_root` (ReviewFindings-2026-07-18 B4): it shared a
    name with `_shared._repo_root()` but NOT its semantics — that one walks
    up from the *current working directory* to the nearest `.git`, while
    the harness must find its fixtures relative to where it is installed,
    regardless of cwd. Same-name-different-behavior is drift bait; the
    rename records that this is intentional, not a leftover copy."""
    return Path(__file__).resolve().parent.parent


def _tenant_security_dir(root: Path) -> Path:
    return root / ".agent-rfc" / "security"


def _resolve_exit(results: list[ControlResult], strict: bool) -> int:
    # Design: pass=green; warn=green unless strict; fail=red.
    # skip (missing runner on Met/Partial) does not fail strict — only Gap
    # controls are promoted to warn/fail before dispatch (see main loop).
    for r in results:
        if r.status == "fail":
            return 1
        if strict and r.status == "warn":
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["smoke", "ci", "full"], default="full")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--framework", choices=["owasp", "nist", "atlas", "iso42001"])
    p.add_argument("--evidence-pack", type=Path)
    args = p.parse_args(argv)

    root = _install_root()
    strict = args.strict or os.environ.get("SECURITY_STRICT", "") == "1"
    registry_path = root / "fixtures" / "security" / "control_registry.json"
    controls = load_control_registry(registry_path)

    if args.mode == "smoke":
        allow = {"SEC-PII-001", "SEC-PII-002", "SEC-AUDIT-001"}
        controls = [c for c in controls if c.id in allow]

    tenant_security = _tenant_security_dir(root)
    template_risk = root / "fixtures" / "security" / "templates" / "risk_register.yaml"
    results: list[ControlResult] = []
    ctx = {
        "root": root,
        "tenant_security": tenant_security,
        "mode": args.mode,
        "strict": strict,
        # Framework self-test: validate shipped template when tenant file absent.
        "use_template_fallback": (
            not (tenant_security / "risk_register.yaml").exists()
            and template_risk.exists()
            and args.mode in ("full", "ci")
            and not strict
        ),
    }
    for control in controls:
        if control.status == "gap":
            gap_status = "fail" if strict else "warn"
            results.append(
                ControlResult(
                    control.id,
                    gap_status,
                    "gap — not yet implemented",
                    {},
                )
            )
            continue
        runner = RUNNERS.get(control.runner)
        if runner is None:
            results.append(
                ControlResult(
                    control.id,
                    "skip",
                    f"runner {control.runner} not implemented",
                    {},
                )
            )
            continue
        results.append(runner(control, ctx))

    if args.evidence_pack:
        write_evidence_pack(args.evidence_pack, controls, results, args.framework)

    return _resolve_exit(results, strict)


if __name__ == "__main__":
    raise SystemExit(main())
