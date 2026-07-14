from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from security.registry import ControlSpec
from security.report import ControlResult


class _SmokeModel(BaseModel):
    answer: str
    score: int


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.structured_output import StructuredOutputError, parse_llm_json

    failures: list[str] = []

    try:
        parsed = parse_llm_json(
            'Here:\n```json\n{"answer":"ok","score":1}\n```',
            _SmokeModel,
        )
        if parsed.answer != "ok" or parsed.score != 1:
            failures.append("fenced parse mismatch")
    except Exception as exc:  # noqa: BLE001 — harness aggregates
        failures.append(f"fenced: {exc}")

    try:
        parse_llm_json('{"answer":"ok"}', _SmokeModel)
        failures.append("invalid schema did not raise")
    except StructuredOutputError:
        pass
    except Exception as exc:  # noqa: BLE001
        failures.append(f"invalid schema wrong error: {exc}")

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
        message="structured_output smoke ok",
        evidence={},
    )
