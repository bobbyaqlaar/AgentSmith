"""
runtime/test/test_input_guardrail.py — pre-call PII scrubbing
(FIXES_AND_CLEANUP.md Security & Guardrails / UAE PDPL).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime import input_guardrail as ig  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_guardrail_state(monkeypatch: pytest.MonkeyPatch) -> None:
    ig.reset_input_guardrail()
    monkeypatch.delenv("INPUT_GUARDRAIL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    yield
    ig.reset_input_guardrail()


def test_default_scrub_masks_emirates_id() -> None:
    text = "Applicant Emirates ID 784-1234-1234567-1 needs review"
    out, counts = ig.scrub_text(text, mode="default")
    assert "784-1234-1234567-1" not in out
    assert "[REDACTED_EMIRATES_ID]" in out
    assert counts.get("emirates_id", 0) >= 1


def test_default_scrub_masks_email_and_phone() -> None:
    text = "Contact ali@example.com or +971501234567"
    out, counts = ig.scrub_text(text, mode="default")
    assert "ali@example.com" not in out
    assert "+971501234567" not in out
    assert "[REDACTED_EMAIL]" in out
    assert "[REDACTED_PHONE]" in out
    assert counts.get("email", 0) >= 1
    assert counts.get("phone", 0) >= 1


def test_off_mode_leaves_text_unchanged() -> None:
    text = "ID 784-1234-1234567-1 and ali@example.com"
    out, counts = ig.scrub_text(text, mode="off")
    assert out == text
    assert counts == {}


def test_scrub_messages_rewrites_content_strings() -> None:
    messages = [
        {"role": "user", "content": "Emirates ID 784-9999-1234567-1"},
        {"role": "system", "content": "You are helpful."},
    ]
    scrubbed, counts = ig.scrub_messages(messages, mode="default")
    assert "784-9999-1234567-1" not in scrubbed[0]["content"]
    assert scrubbed[1]["content"] == "You are helpful."
    assert counts.get("emirates_id", 0) >= 1
    # Original list not mutated
    assert "784-9999-1234567-1" in messages[0]["content"]


def test_custom_callback_replaces_default() -> None:
    def custom(text: str) -> tuple[str, dict[str, int]]:
        return text.replace("SECRET", "[REDACTED_CUSTOM]"), {"custom": 1}

    ig.register_input_guardrail(custom)
    out, counts = ig.scrub_text("keep email ali@example.com SECRET", mode="custom")
    assert "SECRET" not in out
    assert "[REDACTED_CUSTOM]" in out
    assert "ali@example.com" in out  # default patterns not applied in custom-only
    assert counts == {"custom": 1}


def test_resolve_mode_defaults_off_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("INPUT_GUARDRAIL", raising=False)
    assert ig.resolve_mode() == "off"


def test_resolve_mode_defaults_default_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("INPUT_GUARDRAIL", raising=False)
    assert ig.resolve_mode() == "default"


def test_resolve_mode_respects_explicit_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INPUT_GUARDRAIL", "off")
    assert ig.resolve_mode() == "off"
