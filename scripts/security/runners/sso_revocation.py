from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    portal = root / "portal"
    test_file = portal / "test" / "ssoRevocation.test.ts"
    mode_file = portal / "lib" / "ssoRevocationMode.ts"
    middleware = portal / "middleware.ts"

    missing = [p.name for p in (test_file, mode_file, middleware) if not p.exists()]
    if missing:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"missing portal SSO files: {', '.join(missing)}",
            evidence={},
        )

    text = mode_file.read_text(encoding="utf-8") + "\n" + middleware.read_text(encoding="utf-8")
    required_snippets = (
        "SSO_REVOCATION_MODE",
        "fail-closed",
        "fail-open",
        "503",
    )
    absent = [s for s in required_snippets if s not in text]
    if absent:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"SSO revocation mode snippets missing: {', '.join(absent)}",
            evidence={},
        )

    proc = subprocess.run(
        ["node", "--experimental-strip-types", str(test_file)],
        cwd=portal,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="ssoRevocation.test.ts failed",
            evidence={"stderr": (proc.stderr or proc.stdout)[:500]},
        )

    return ControlResult(
        control_id=control.id,
        status="pass",
        message="SSO_REVOCATION_MODE fail-open/fail-closed tests passed",
        evidence={"test": str(test_file.relative_to(root))},
    )
