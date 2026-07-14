from __future__ import annotations

from collections.abc import Callable
from typing import Any

from security.registry import ControlSpec
from security.report import ControlResult
from security.runners import (
    adversarial_eval,
    moderation_hook,
    noop,
    pii_postcall,
    pii_precall,
    prompt_guard,
    risk_register,
    sso_revocation,
    structured_output,
    tool_allowlist,
)

Runner = Callable[[ControlSpec, dict[str, Any]], ControlResult]

RUNNERS: dict[str, Runner] = {
    "noop": noop.run,
    "pii_precall": pii_precall.run,
    "pii_postcall": pii_postcall.run,
    "prompt_guard": prompt_guard.run,
    "risk_register": risk_register.run,
    "structured_output": structured_output.run,
    "tool_allowlist": tool_allowlist.run,
    "adversarial_eval": adversarial_eval.run,
    "moderation_hook": moderation_hook.run,
    "sso_revocation": sso_revocation.run,
}
