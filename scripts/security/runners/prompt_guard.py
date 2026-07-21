"""SEC-PROMPT-001 runner — prompt-injection detection AND enforcement.

Two things are checked, because passing only the first is how a control
reports "Met" while nothing is actually blocked in production
(TestbedFeedback-2026-07-21 G9):

  1. Detection — the heuristics classify the fixture corpus correctly.
  2. Enforcement — the configured PROMPT_GUARD mode actually blocks. A
     tenant running the observe-first `warn` tier is deliberately NOT
     enforcing, so that is reported as a warn (visible, and a strict-CI
     failure) rather than a silent pass.
"""

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

    from runtime.prompt_guard import is_enforcing, resolve_mode, scan_prompt

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

    # ── Enforcement ──────────────────────────────────────────────────────
    # Detection alone proves the heuristics work, not that anything is
    # blocked. `off` is a real gap; `warn` is a legitimate rollout posture
    # but still not enforcement, so both surface rather than passing.
    mode = resolve_mode()
    evidence = {"cases": str(len(cases)), "mode": mode}

    if mode == "off":
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=(
                f"detection passed {len(cases)} cases but PROMPT_GUARD=off — "
                "no prompt is scanned in this environment"
            ),
            evidence=evidence,
        )

    if not is_enforcing(mode):
        return ControlResult(
            control_id=control.id,
            status="warn",
            message=(
                f"detection passed {len(cases)} cases; PROMPT_GUARD={mode} reports "
                "without blocking (observe-first tier). Set PROMPT_GUARD=default "
                "to enforce before promoting to production."
            ),
            evidence=evidence,
        )

    return ControlResult(
        control_id=control.id,
        status="pass",
        message=f"prompt_guard passed {len(cases)} cases; enforcing (mode={mode})",
        evidence=evidence,
    )
