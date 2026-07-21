"""
runtime/input_guardrail.py — pre-call PII scrubbing for LLM prompts.

Symmetric to trace_redactor.py (post-call observability scrubbing): this
module runs **before** provider invoke so personal data is masked in the
decision path (UAE PDPL / FIXES Security & Guardrails).

Modes (INPUT_GUARDRAIL env, else environment-derived default):
  off      — no-op
  default  — framework regex scrubbers (Emirates ID, email, phone, cards)
  custom   — tenant callback registered via register_input_guardrail()

Default when unset: off in development, default in staging/production.
"""

from __future__ import annotations

import copy
import logging
import os
import re
from collections.abc import Callable
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from runtime.environment import get_environment
except ImportError:  # pragma: no cover
    from environment import get_environment  # type: ignore

# ── Types ─────────────────────────────────────────────────────────────────────

ScrubFn = Callable[[str], tuple[str, dict[str, int]]]

_custom_scrubber: Optional[ScrubFn] = None

# Emirates ID: 784-XXXX-XXXXXXX-X (hyphenated) or 15 digits starting with 784
_EMIRATES_ID_HYPHEN = re.compile(
    r"\b784-\d{4}-\d{7}-\d\b",
)
_EMIRATES_ID_DIGITS = re.compile(
    r"\b784\d{12}\b",
)
_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# UAE / intl phones: +971… or 00… or long digit runs with optional separators
_PHONE = re.compile(
    r"(?<!\d)(?:\+|00)?(?:971[\s-]?)?(?:0?5\d|5\d)[\s-]?\d{3}[\s-]?\d{4}\b"
    r"|(?<!\d)\+\d{10,15}\b"
)
_CARD_CANDIDATE = re.compile(r"(?:\d[ -]?){13,19}")


# Shared with trace_redactor.py — one Luhn implementation for both the
# pre-call guard and the post-call redactor (ReviewFindings-2026-07-18 B1).
try:
    from runtime.luhn import luhn_valid as _luhn_valid
except ImportError:  # pragma: no cover — flat (non-package) import layout
    from luhn import luhn_valid as _luhn_valid  # type: ignore


def reset_input_guardrail() -> None:
    """Clear tenant callback — for tests."""
    global _custom_scrubber
    _custom_scrubber = None


def register_input_guardrail(fn: ScrubFn) -> None:
    """Replace default scrubbing when mode=custom (or call from tenant init)."""
    global _custom_scrubber
    _custom_scrubber = fn


def resolve_mode() -> str:
    raw = os.environ.get("INPUT_GUARDRAIL", "").strip().lower()
    if raw in {"off", "default", "custom"}:
        return raw
    if get_environment() == "development":
        return "off"
    return "default"


def scrub_text(text: str, mode: Optional[str] = None) -> tuple[str, dict[str, int]]:
    """Scrub a single string. Returns (scrubbed_text, counts_by_type)."""
    active = mode or resolve_mode()
    if active == "off":
        return text, {}
    if active == "custom":
        if _custom_scrubber is None:
            logger.warning(
                "INPUT_GUARDRAIL=custom but no scrubber registered — leaving text unchanged"
            )
            return text, {}
        return _custom_scrubber(text)
    return _default_scrub(text)


def _default_scrub(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    out = text

    def _sub_emirates_hyphen(m: re.Match[str]) -> str:
        counts["emirates_id"] = counts.get("emirates_id", 0) + 1
        return "[REDACTED_EMIRATES_ID]"

    def _sub_emirates_digits(m: re.Match[str]) -> str:
        counts["emirates_id"] = counts.get("emirates_id", 0) + 1
        return "[REDACTED_EMIRATES_ID]"

    def _sub_email(m: re.Match[str]) -> str:
        counts["email"] = counts.get("email", 0) + 1
        return "[REDACTED_EMAIL]"

    def _sub_phone(m: re.Match[str]) -> str:
        counts["phone"] = counts.get("phone", 0) + 1
        return "[REDACTED_PHONE]"

    def _sub_card(m: re.Match[str]) -> str:
        if _luhn_valid(m.group(0)):
            counts["card"] = counts.get("card", 0) + 1
            return "[REDACTED_CARD]"
        return m.group(0)

    out = _EMIRATES_ID_HYPHEN.sub(_sub_emirates_hyphen, out)
    out = _EMIRATES_ID_DIGITS.sub(_sub_emirates_digits, out)
    out = _EMAIL.sub(_sub_email, out)
    out = _PHONE.sub(_sub_phone, out)
    out = _CARD_CANDIDATE.sub(_sub_card, out)
    return out, counts


def scrub_messages(
    messages: list[dict[str, Any]],
    mode: Optional[str] = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Deep-copy messages and scrub string `content` fields.
    Does not mutate the input list.
    """
    active = mode or resolve_mode()
    if active == "off":
        return copy.deepcopy(messages), {}

    total: dict[str, int] = {}
    out = copy.deepcopy(messages)
    for msg in out:
        content = msg.get("content")
        if isinstance(content, str):
            scrubbed, counts = scrub_text(content, mode=active)
            msg["content"] = scrubbed
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
        elif isinstance(content, list):
            # OpenAI-style multimodal content parts
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    scrubbed, counts = scrub_text(part["text"], mode=active)
                    part["text"] = scrubbed
                    for k, v in counts.items():
                        total[k] = total.get(k, 0) + v
    return out, total
