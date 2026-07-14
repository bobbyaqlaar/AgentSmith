from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    script = root / "scripts" / "verify_system.py"
    # Force staging so development ENVIRONMENT cannot skip the redaction check.
    env = {**os.environ, "ENVIRONMENT": "staging"}
    proc = subprocess.run(
        [sys.executable, str(script), "--check-redaction"],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="verify_system --check-redaction failed",
            evidence={"stderr": (proc.stderr or proc.stdout)[:500]},
        )
    return ControlResult(
        control_id=control.id,
        status="pass",
        message="verify_system --check-redaction passed",
        evidence={},
    )
