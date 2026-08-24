"""
runtime/test/test_trace_redactor.py — regression tests for trace redaction
(SPECS.md §27, Product_Archive.md 1.2 / 2.2 / 2.3 / 2.8).

No external infra required — these exercise TraceRedactor's pure scrubbing
logic and the per-span tenant binding directly, without a real OTel SDK
span. opentelemetry-sdk is in requirements.txt, so _HAS_OTEL is expected
True in CI; if it's somehow absent these tests are skipped rather than
failing for an unrelated reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime import trace_redactor as tr  # noqa: E402
from runtime.environment import get_environment  # noqa: E402

pytestmark = pytest.mark.skipif(
    not tr._HAS_OTEL, reason="opentelemetry-sdk not installed"
)


class FakeSpanContext:
    def __init__(self, trace_id: int, span_id: int):
        self.trace_id = trace_id
        self.span_id = span_id


class FakeSpan:
    """Minimal stand-in for opentelemetry.sdk.trace.ReadableSpan — only the
    attributes TraceRedactor.on_end() actually reads."""

    def __init__(self, attributes: dict, trace_id: int = 1, span_id: int = 1):
        self._attributes = dict(attributes)
        self.context = FakeSpanContext(trace_id, span_id)


def _redactor(profile: str, tenant_id: str = "unknown", **kw) -> tr.TraceRedactor:
    return tr.TraceRedactor(profile=profile, tenant_id=tenant_id, **kw)


def test_staging_profile_hashes_secrets_preserving_structure():
    redactor = _redactor("staging")
    span = FakeSpan(
        {
            "input.value": "Authorization: Bearer sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
        }
    )
    redactor.on_end(span)
    scrubbed = span._attributes["input.value"]
    assert "sk-ant-" not in scrubbed
    assert "[REDACTED:" in scrubbed  # hashed marker, not a flat redaction


def test_production_profile_truncates_and_flattens():
    redactor = _redactor("production", tenant_id="acme")
    long_value = "x" * 200 + " contact someone@example.com for help"
    span = FakeSpan({"input.value": long_value})
    redactor.on_end(span)
    scrubbed = span._attributes["input.value"]
    assert len(scrubbed) <= 50 + len("…[truncated]")
    assert "@example.com" not in scrubbed


def test_development_profile_does_not_scrub():
    redactor = _redactor("development")
    span = FakeSpan({"input.value": "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"})
    redactor.on_end(span)
    assert (
        span._attributes["input.value"] == "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
    )


def test_unrecognized_profile_value_falls_back_to_strictest():
    """Product_Archive.md 2.8: an unrecognized profile string passed
    directly must resolve to the strictest behavior, not the most
    permissive — mirrors get_environment()'s own fail-closed contract."""
    redactor = _redactor("totally-bogus-value")
    assert redactor.profile == "production"


def test_per_span_tenant_id_used_for_hitl_blob_not_constructor_default(
    tmp_path, monkeypatch
):
    """Product_Archive.md 1.2: the regression this guards against is a
    shared worker pool binding tenant_id once at construction time and
    leaking tenant A's HITL blob under tenant B's key (or vice versa)."""
    monkeypatch.setenv("HITL_BLOB_DIR", str(tmp_path))
    monkeypatch.setenv("HITL_ENCRYPTION_KEY", "test-key-not-a-real-secret")

    # Constructed with a default/fallback tenant_id of "default-tenant" —
    # the span itself carries a DIFFERENT tenant.id attribute, which must win.
    redactor = _redactor("production", tenant_id="default-tenant")
    payload = "x" * 100  # > 50 chars, triggers the HITL blob path
    span = FakeSpan(
        {"input.value": payload, "tenant.id": "real-tenant"}, trace_id=42, span_id=7
    )
    redactor.on_end(span)

    assert (tmp_path / "real-tenant").is_dir(), (
        "blob was not stored under the span's own tenant.id"
    )
    assert not (tmp_path / "default-tenant").exists(), (
        "blob was incorrectly stored under the constructor fallback tenant_id"
    )


def test_blob_ref_includes_span_id_for_collision_safety(tmp_path, monkeypatch):
    """Product_Archive.md 2.2: two sibling spans in the same trace with
    the same attr_key must not collide on the same blob ref."""
    monkeypatch.setenv("HITL_BLOB_DIR", str(tmp_path))
    monkeypatch.setenv("HITL_ENCRYPTION_KEY", "test-key-not-a-real-secret")

    redactor = _redactor("production", tenant_id="acme")
    payload = "y" * 100
    span_a = FakeSpan({"input.value": payload}, trace_id=99, span_id=1)
    span_b = FakeSpan({"input.value": payload}, trace_id=99, span_id=2)
    redactor.on_end(span_a)
    redactor.on_end(span_b)

    ref_a = span_a._attributes["input.value.hitl_blob_ref"]
    ref_b = span_b._attributes["input.value.hitl_blob_ref"]
    assert ref_a != ref_b, (
        "sibling spans in the same trace collided on the same blob ref"
    )

    blob_dir = tmp_path / "acme"
    written = {p.stem for p in blob_dir.glob("*.json")}
    assert len(written) == 2, f"expected 2 distinct blob files, got {written}"


def test_missing_hitl_key_logs_error_not_silently_swallowed(
    tmp_path, monkeypatch, caplog
):
    """Product_Archive.md 2.3: a missing HITL_ENCRYPTION_KEY must be
    visible (logged), not a silently dropped blob with a dangling ref."""
    monkeypatch.setenv("HITL_BLOB_DIR", str(tmp_path))
    monkeypatch.delenv("HITL_ENCRYPTION_KEY", raising=False)

    redactor = _redactor("production", tenant_id="acme")
    payload = "z" * 100
    span = FakeSpan({"input.value": payload})

    import logging

    with caplog.at_level(logging.ERROR, logger="runtime.trace_redactor"):
        redactor.on_end(span)

    assert any(
        "NOT written" in rec.message or "HITL" in rec.message for rec in caplog.records
    ), "missing-key failure was not logged at ERROR level"
    # truncation still happens — the span is still safe to export
    assert len(span._attributes["input.value"]) <= 50 + len("…[truncated]")


def test_credit_card_redaction_validates_luhn():
    redactor = _redactor("staging")
    valid_card = "4111-1111-1111-1111"  # Luhn-valid test number
    invalid_card = "1234-5678-9012-3456"  # Luhn-invalid — looks card-shaped but isn't
    span = FakeSpan({"input.value": f"card {valid_card} and also {invalid_card}"})
    redactor.on_end(span)
    scrubbed = span._attributes["input.value"]
    assert valid_card not in scrubbed
    assert invalid_card in scrubbed  # not Luhn-valid -> not touched


def test_get_environment_fail_closed_for_unrecognized_value(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "not-a-real-environment")
    assert get_environment() == "production"


def test_get_environment_fail_closed_for_unset(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert get_environment() == "production"


def test_get_environment_explicit_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert get_environment() == "development"


# ── against a REAL span, which is where this was broken ──────────────────────


def _isolated_provider(profile: str):
    """A TracerProvider that is never registered globally.

    Isolated for two reasons found the hard way: an OTel processor can be added
    to a provider and never removed, so attaching a redactor to the shared one
    scrubs every later test in the run; and `set_tracer_provider` is one-shot,
    so a second global provider is silently ignored.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(tr.TraceRedactor(profile=profile, tenant_id="acme"))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_real_span_is_scrubbed_end_to_end():
    """The test this module did not have, and the reason it mattered.

    Every other test here drives `on_end` with a FakeSpan whose `_attributes`
    is a plain dict. The SDK hands processors a ReadableSpan whose attributes
    are `BoundedAttributes(immutable=True)`, and writing to those raises a bare
    TypeError out of `span.end()` — so against a real span this processor
    redacted NOTHING and made ending a span throw. Every test passed, because
    the double accepted writes the real object refuses.

    That is the first entry in this repo's lessons appendix, in the redaction
    control: a test double must never be more capable than the real thing.
    """
    provider, exporter = _isolated_provider("staging")
    secret = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"

    with provider.get_tracer("t").start_as_current_span("llm.call") as span:
        span.set_attribute("input.value", f"key={secret} card=4111111111111111")
        span.set_attribute("agent.tool.name", "payment_lookup")

    attributes = dict(exporter.get_finished_spans()[0].attributes)
    assert secret not in attributes["input.value"]
    assert "4111111111111111" not in attributes["input.value"]
    assert "[REDACTED" in attributes["input.value"]
    # A non-payload attribute keeps its value.
    assert attributes["agent.tool.name"] == "payment_lookup"


def test_ending_a_span_with_the_redactor_installed_does_not_raise():
    """The other half of the same bug, and the worse one operationally: the
    TypeError propagated out of `span.end()`, so a worker with the redactor
    installed — which `configure_tracing()` does by default — would have raised
    on every span it closed."""
    provider, _ = _isolated_provider("production")
    with provider.get_tracer("t").start_as_current_span("llm.call") as span:
        span.set_attribute("input.value", "x" * 200)
    # Reaching here at all is the assertion.


def test_development_profile_leaves_a_real_span_alone():
    """The permissive profile must still be permissive against the real object,
    not merely against the double."""
    provider, exporter = _isolated_provider("development")
    with provider.get_tracer("t").start_as_current_span("llm.call") as span:
        span.set_attribute("input.value", "card=4111111111111111")

    assert "4111111111111111" in dict(exporter.get_finished_spans()[0].attributes)["input.value"]
