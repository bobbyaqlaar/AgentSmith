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
import re
from collections.abc import Callable
from typing import Any, Optional

from runtime.environment import get_environment

logger = logging.getLogger(__name__)

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
from runtime.luhn import luhn_valid as _luhn_valid  # noqa: E402 — sited beside the comment explaining the sharing


def reset_input_guardrail() -> None:
    """Clear tenant callback — for tests."""
    global _custom_scrubber
    _custom_scrubber = None


def register_input_guardrail(fn: ScrubFn) -> None:
    """Replace default scrubbing when mode=custom (or call from tenant init)."""
    global _custom_scrubber
    _custom_scrubber = fn


def resolve_mode() -> str:
    from runtime.config import resolve

    raw = str(
        resolve("security.input_guardrail", env_var="INPUT_GUARDRAIL", default="")
    ).strip().lower()
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

    def _redactor(label: str, replacement: str):
        """Count a hit under `label` and replace it.

        Four of these were written out separately and differed only in those
        two strings — which meant the counter key and the redaction token could
        drift apart, and `guardrail_counts` is evidence a tenant records in its
        own decision record (every PDPL/GDPR decision-path app). Pairing them in
        one place is what keeps a count of "email" from labelling something
        redacted as a phone number.
        """

        def _sub(m: "re.Match[str]") -> str:
            counts[label] = counts.get(label, 0) + 1
            return replacement

        return _sub

    def _sub_card(m: "re.Match[str]") -> str:
        # Not built by _redactor: a card candidate is only redacted if it
        # passes Luhn, so this one can decline to substitute — and must not
        # count when it does.
        if _luhn_valid(m.group(0)):
            counts["card"] = counts.get("card", 0) + 1
            return "[REDACTED_CARD]"
        return m.group(0)

    # Order matters: the hyphenated Emirates ID pattern runs before the
    # bare-digit one so the more specific form is consumed first.
    for pattern, label, replacement in (
        (_EMIRATES_ID_HYPHEN, "emirates_id", "[REDACTED_EMIRATES_ID]"),
        (_EMIRATES_ID_DIGITS, "emirates_id", "[REDACTED_EMIRATES_ID]"),
        (_EMAIL, "email", "[REDACTED_EMAIL]"),
        (_PHONE, "phone", "[REDACTED_PHONE]"),
    ):
        out = pattern.sub(_redactor(label, replacement), out)
    out = _CARD_CANDIDATE.sub(_sub_card, out)
    return out, counts


def detect_pii(text: str) -> dict[str, int]:
    """Count PII occurrences by type WITHOUT rewriting the text.

    `scrub_text` answers "what may I send to the model". This answers "does
    this text contain PII at all", which is what an OUTPUT-side check needs —
    a tenant moderation hook asserting a model didn't reconstruct into its
    answer what the pre-call guard stripped from the prompt, or an audit
    assertion over a stored rationale.

    It delegates to `_default_scrub` and discards the rewritten text, so the
    two sides cannot disagree about what counts as an Emirates ID or a card.
    Re-deriving the patterns in the output check is exactly the divergence
    runtime/luhn.py was extracted to prevent (ReviewFindings-2026-07-18 B1):
    a hand-rolled `(?:\\d[ -]?){13,19}` with no Luhn call flags any long digit
    run — an invoice number, a registry filing reference — that the pre-call
    guard deliberately leaves alone.

    Ignores INPUT_GUARDRAIL mode: "is there PII in this text" is a question
    about the text, not about whether prompts are currently being scrubbed.
    """
    _, counts = _default_scrub(text or "")
    return counts


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
