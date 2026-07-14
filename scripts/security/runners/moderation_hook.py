from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult


def run(control: ControlSpec, ctx: dict[str, Any]) -> ControlResult:
    root = Path(ctx["root"])
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from runtime import moderation as mod

    mod.reset_output_moderator()
    strict = bool(ctx.get("strict", False)) or os.environ.get("SECURITY_STRICT", "") == "1"
    mode = os.environ.get("MODERATION_HOOK", "").strip().lower()

    # API smoke: register classifier, allow clean, block unsafe.
    mod.register_output_moderator(
        lambda t: mod.ModerationResult(
            allowed="unsafe" not in t.lower(),
            reasons=["policy"] if "unsafe" in t.lower() else [],
        )
    )
    try:
        ok = mod.apply_output_moderation("safe output")
        bad = mod.apply_output_moderation("unsafe payload")
        try:
            mod.apply_output_moderation("unsafe payload", raise_on_block=True)
            raised = False
        except mod.ModerationBlockedError:
            raised = True
    finally:
        mod.reset_output_moderator()

    if not ok.allowed or bad.allowed or not raised:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="moderator smoke failed",
            evidence={},
        )

    # Prove required mode rejects missing registration.
    try:
        mod.apply_output_moderation("x", mode="required")
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="required mode did not raise without hook",
            evidence={},
        )
    except mod.ModerationHookRequiredError:
        pass

    # Tenant ownership:
    # - MODERATION_HOOK=required → fail without a durable tenant registration
    # - strict + unset → fail (forces explicit optional/required/off)
    # - optional/off → pass after API smoke (even under SECURITY_STRICT)
    # - unset + non-strict → warn
    if mode == "required":
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="no output moderator registered (MODERATION_HOOK=required)",
            evidence={"mode": mode},
        )
    if mode in ("optional", "off"):
        return ControlResult(
            control_id=control.id,
            status="pass",
            message=f"moderation API smoke ok (MODERATION_HOOK={mode})",
            evidence={"mode": mode},
        )
    if strict:
        return ControlResult(
            control_id=control.id,
            status="fail",
            message="no output moderator registered (strict; set MODERATION_HOOK=optional|required|off)",
            evidence={"mode": "unset"},
        )

    return ControlResult(
        control_id=control.id,
        status="warn",
        message="moderation hook unset (optional) — tenant should register for regulated content",
        evidence={"mode": "unset"},
    )
