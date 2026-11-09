"""OpenTelemetry's GenAI names beside the contract's own (.agent-rfc/designs/gen-ai-telemetry.md)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentsmith import telemetry_contract as tc

pytest.importorskip("opentelemetry.sdk")
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.mark.parametrize("model, provider", [
    ("gemini/gemini-3-flash-preview", "gcp.gemini"), ("ollama/falcon3:3b", "ollama"),
    ("ollama_chat/llama3", "ollama"), ("bedrock/anthropic.claude", "aws.bedrock"),
    ("anthropic/claude-sonnet-5-5", "anthropic"), ("openrouter/x/y", "openrouter"), ("XAI/grok", "x_ai"),
])
def test_a_provider_is_named_as_the_conventions_name_it(model, provider):
    assert tc.genai_provider(model) == provider


@pytest.mark.parametrize("model", ["gpt-4o", "", "/model"])
def test_an_id_naming_no_provider_names_none(model):
    assert tc.genai_provider(model) is None


def _span(**kw):
    from agentsmith.llm_gateway import LLMGateway

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.tenant_id = "t"
    with provider.get_tracer("t").start_as_current_span("llm.call") as span:
        arguments = dict(model_id="gemini/gemini-3-flash-preview", role="judge", cost_usd=0.0, ttft_ms=None,
                         degrade_tier=None, workflow_id=None, input_tokens=3, output_tokens=5, cost_estimated=False)
        arguments.update(kw)
        gateway._stamp_llm_span(span, **arguments)
    return dict(exporter.get_finished_spans()[0].attributes)


def test_a_gateway_span_carries_both_names():
    attributes = _span()
    assert attributes["gen_ai.operation.name"] == "chat"
    assert attributes["gen_ai.request.model"] == attributes["llm.model_name"] == "gemini/gemini-3-flash-preview"
    assert attributes["gen_ai.provider.name"] == "gcp.gemini"
    assert attributes["gen_ai.usage.input_tokens"] == attributes["llm.usage.input_tokens"] == 3
    assert attributes["gen_ai.usage.output_tokens"] == attributes["llm.usage.output_tokens"] == 5


def test_unreported_usage_writes_no_genai_count():
    attributes = _span(input_tokens=None, output_tokens=None)
    assert "gen_ai.usage.input_tokens" not in attributes and "gen_ai.usage.output_tokens" not in attributes


def test_an_id_with_no_provider_writes_no_provider():
    assert "gen_ai.provider.name" not in _span(model_id="gpt-4o")


def test_a_tool_span_carries_both_names(monkeypatch):
    from opentelemetry import trace

    from agentsmith import tracing

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", lambda *a, **k: provider.get_tracer("t"))
    with provider.get_tracer("t").start_as_current_span("agent.step"):
        tracing.record_tool_call("lookup", allowed=True, duration_ms=1.0)
    tool = next(s for s in exporter.get_finished_spans() if s.name.startswith("agent.tool."))
    assert tool.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool.attributes["gen_ai.tool.name"] == tool.attributes["agent.tool.name"] == "lookup"


def test_the_pin_is_in_the_protocol():
    protocol = (Path(__file__).resolve().parents[2] / "contract" / "telemetry" / "v1" / "protocol.md").read_text(
        encoding="utf-8")
    commit = tc.GENAI_CONVENTIONS.split("@", 1)[1].split()[0]
    assert commit in protocol
