"""
runtime/moderation.py — pluggable output moderation hook (SEC-MOD-001).

Modes (MODERATION_HOOK env):
  off       — never call hook
  optional  — default; no hook → skip/allow; hook present → enforce
  required  — no hook → ModerationHookRequiredError (regulated tenants / strict CI)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

ModeratorFn = Callable[[str], "ModerationResult"]

_moderator: Optional[ModeratorFn] = None


class ModerationHookRequiredError(RuntimeError):
    """Raised when MODERATION_HOOK=required and no moderator is registered."""


class ModerationBlockedError(RuntimeError):
    """Raised when the registered moderator rejects output text."""

    def __init__(self, message: str, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.reasons = reasons or []


@dataclass(frozen=True)
class ModerationResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    skipped: bool = False


def reset_output_moderator() -> None:
    """Clear tenant moderator — for tests."""
    global _moderator
    _moderator = None


def register_output_moderator(fn: ModeratorFn) -> None:
    """Register a tenant classifier for LLM output text."""
    global _moderator
    _moderator = fn


def get_output_moderator() -> Optional[ModeratorFn]:
    return _moderator


def resolve_mode() -> str:
    raw = os.environ.get("MODERATION_HOOK", "").strip().lower()
    if raw in {"off", "optional", "required"}:
        return raw
    return "optional"


def apply_output_moderation(
    text: str,
    *,
    raise_on_block: bool = False,
    mode: Optional[str] = None,
) -> ModerationResult:
    """
    Run the registered moderator (if any) against ``text``.

    - off: always allow (skipped)
    - optional + no hook: allow (skipped)
    - required + no hook: raise ModerationHookRequiredError
    - hook present + blocked: return allowed=False; optionally raise
    """
    active = mode or resolve_mode()
    if active == "off":
        return ModerationResult(allowed=True, skipped=True)

    if _moderator is None:
        if active == "required":
            raise ModerationHookRequiredError(
                "MODERATION_HOOK=required but no output moderator registered"
            )
        return ModerationResult(allowed=True, skipped=True)

    result = _moderator(text)
    if not result.allowed:
        if raise_on_block:
            raise ModerationBlockedError(
                f"output blocked: {', '.join(result.reasons) or 'policy'}",
                reasons=list(result.reasons),
            )
        return ModerationResult(allowed=False, reasons=list(result.reasons), skipped=False)
    return ModerationResult(allowed=True, reasons=list(result.reasons), skipped=False)
