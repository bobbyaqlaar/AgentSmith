from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult
from security.runners._shared import framework_root


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    # framework_root inserts the repo ROOT only. The previous version also
    # inserted root/runtime, which would let `import input_guardrail` resolve
    # flat — nothing does that (runtime modules import each other as
    # `runtime.X`), and a bare runtime/ on sys.path can shadow same-named
    # top-level modules. Vestigial from before the package rename.
    root = framework_root(ctx)

    from runtime.input_guardrail import scrub_text

    cases_path = root / "fixtures" / "security" / "pii_probe_cases_base.json"
    if not cases_path.exists():
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"missing probe fixtures: {cases_path}",
            evidence={},
        )

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        scrubbed, _counts = scrub_text(case["input"], mode="default")
        for needle in case.get("must_not_contain", []):
            if needle in scrubbed:
                failures.append(f"{case['id']}: still contains {needle!r}")
        for needle in case.get("must_contain", []):
            if needle not in scrubbed:
                failures.append(f"{case['id']}: missing {needle!r}")

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
        message=f"scrubbed {len(cases)} probe cases",
        evidence={"cases": str(len(cases))},
    )
