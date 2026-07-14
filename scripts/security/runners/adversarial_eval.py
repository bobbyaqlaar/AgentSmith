from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult


def _load_run_evals(root: Path):
    path = root / "scripts" / "run-evals.py"
    spec = importlib.util.spec_from_file_location("run_evals_harness", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

    revals = _load_run_evals(root)
    cases = revals._load_cases("adversarial")
    if len(cases) < 3:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"need ≥3 adversarial cases, found {len(cases)}",
            evidence={},
        )

    results = [revals.score_adversarial_case(c) for c in cases]
    miss = revals.adversarial_miss_rate(results)
    limit = revals._resolve_adversarial_fail_above(None)
    if miss > limit:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"adversarial miss rate {miss:.3f} > {limit:.3f}",
            evidence={"miss_rate": f"{miss:.3f}", "limit": f"{limit:.3f}"},
        )
    return ControlResult(
        control_id=control.id,
        status="pass",
        message=f"adversarial miss rate {miss:.3f} ≤ {limit:.3f} ({len(cases)} cases)",
        evidence={"miss_rate": f"{miss:.3f}", "cases": str(len(cases))},
    )
