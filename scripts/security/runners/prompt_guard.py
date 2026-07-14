from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.prompt_guard import scan_prompt

    cases_path = root / "fixtures" / "security" / "prompt_injection_cases_base.json"
    if not cases_path.exists():
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"missing fixture: {cases_path}",
            evidence={},
        )

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        result = scan_prompt(case["input"])
        expected = bool(case["expect_blocked"])
        if result.blocked != expected:
            failures.append(
                f"{case['id']}: expected blocked={expected} got {result.blocked}"
            )

    if failures:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="; ".join(failures[:5]),
            evidence={"failures": str(len(failures))},
        )
    return ControlResult(
        control_id=control.id,
        status="pass",
        message=f"prompt_guard passed {len(cases)} cases",
        evidence={"cases": str(len(cases))},
    )
