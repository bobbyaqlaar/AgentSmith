"""
runtime/prompt_guard.py — pre-call prompt-injection heuristics (SEC-PROMPT-001).

Modes (PROMPT_GUARD env):
  off      — no-op
  default  — scan; block returns PromptGuardResult(blocked=True); gateway may log
  strict   — scan; gateway raises PromptGuardBlockedError on block

Optional tenant denylist: .agent-rfc/security/prompt_denylist.txt
or PROMPT_DENYLIST_PATH.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class PromptGuardBlockedError(RuntimeError):
    """Raised when PROMPT_GUARD=strict and scan_prompt blocks the input."""

    def __init__(self, message: str, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.reasons = reasons or []


@dataclass(frozen=True)
class PromptGuardResult:
    blocked: bool
    reasons: list[str] = field(default_factory=list)


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "instruction_override",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "instruction_override",
        re.compile(
            r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_system",
        re.compile(
            r"(reveal|show|print|dump)\s+(the\s+)?(system\s+prompt|hidden\s+instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_marker",
        re.compile(
            r"(?m)^(system|assistant)\s*:\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "delimiter_injection",
        re.compile(
            r"(```\s*system|<\s*/?\s*system\s*>|\[INST\]|<<\s*SYS\s*>>)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"\b(dan\s*mode|developer\s*mode\s*enabled|jailbreak)\b",
            re.IGNORECASE,
        ),
    ),
]


def resolve_mode() -> str:
    raw = os.environ.get("PROMPT_GUARD", "").strip().lower()
    if raw in {"off", "default", "strict"}:
        return raw
    return "default"


def _denylist_path() -> Optional[Path]:
    env = os.environ.get("PROMPT_DENYLIST_PATH", "").strip()
    if env:
        return Path(env)
    candidate = Path(".agent-rfc") / "security" / "prompt_denylist.txt"
    if candidate.exists():
        return candidate
    return None


def _load_denylist() -> list[str]:
    path = _denylist_path()
    if path is None or not path.exists():
        return []
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            lines.append(item.lower())
    return lines


def _control_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    control = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\r\t")
    return control / len(text)


def scan_prompt(
    text: str,
    *,
    raise_on_block: bool = False,
    denylist: Optional[list[str]] = None,
) -> PromptGuardResult:
    """Scan text for prompt-injection heuristics."""
    reasons: list[str] = []
    lowered = text.lower()

    for label, pattern in _PATTERNS:
        if pattern.search(text):
            reasons.append(label)

    if _control_char_ratio(text) > 0.05:
        reasons.append("excessive_control_chars")

    deny = denylist if denylist is not None else _load_denylist()
    for item in deny:
        if item and item in lowered:
            reasons.append(f"denylist:{item}")

    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    blocked = bool(uniq)
    if blocked and raise_on_block:
        raise PromptGuardBlockedError(
            f"prompt blocked: {', '.join(uniq)}",
            reasons=uniq,
        )
    return PromptGuardResult(blocked=blocked, reasons=uniq)


def scan_messages(
    messages: list[dict[str, Any]],
    *,
    raise_on_block: bool = False,
) -> PromptGuardResult:
    parts: list[str] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
    return scan_prompt("\n".join(parts), raise_on_block=raise_on_block)


def apply_prompt_guard(messages: list[dict[str, Any]]) -> PromptGuardResult:
    """
    Gateway helper. Respects PROMPT_GUARD mode.
    - off: no-op pass
    - default: scan; return result (caller may log); does not raise
    - strict: scan; raise PromptGuardBlockedError when blocked
    """
    mode = resolve_mode()
    if mode == "off":
        return PromptGuardResult(blocked=False, reasons=[])
    return scan_messages(messages, raise_on_block=(mode == "strict"))
