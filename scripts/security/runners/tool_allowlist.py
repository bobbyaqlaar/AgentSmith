from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime.tool_registry import ToolNotAllowedError, ToolRegistry, tool

    template = root / "fixtures" / "security" / "templates" / "tool_allowlist.yaml"
    if not template.exists():
        return ControlResult(
            control_id=control.id,
            status="fail",
            message=f"missing template: {template}",
            evidence={},
        )

    registry = ToolRegistry(allowlist_path=template, strict=True)

    @tool(name="example_tool", description="template allowlisted", registry=registry)
    def example_tool() -> str:
        return "ok"

    @tool(name="not_allowed", description="should deny", registry=registry)
    def not_allowed() -> str:
        return "bad"

    failures: list[str] = []
    try:
        if registry.invoke("example_tool", {}) != "ok":
            failures.append("allowed invoke mismatch")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"allowed invoke failed: {exc}")

    try:
        registry.invoke("not_allowed", {})
        failures.append("disallowed invoke did not raise")
    except ToolNotAllowedError:
        pass
    except Exception as exc:  # noqa: BLE001
        failures.append(f"disallowed wrong error: {exc}")

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
        message="tool allowlist enforce ok",
        evidence={"template": str(template)},
    )
