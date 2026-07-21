"""
runtime/tracing.py — span helpers for tenant pipeline steps
(TestbedFeedback-2026-07-21 G8).

The gateway emits richly-attributed spans for LLM calls, but a tenant's
NON-LLM steps — tool invocations, scrub counts, judge verdicts, HITL
decisions — had no framework-provided way onto a span. The observability
story is "every token and tool call streamed to Phoenix", yet tool calls
through `ToolRegistry.invoke()` emitted nothing. This closes both halves:
`ToolRegistry.invoke` is instrumented (see tool_registry.py), and
`agent_span()` gives tenant code the same one-liner for its own steps.

Everything degrades to a no-op when opentelemetry isn't installed or no
tracer is configured, exactly like the gateway's own span code — tracing
must never change program behavior or raise into a business path.

    from runtime.tracing import agent_span

    with agent_span("research.sanctions_lookup", tenant_id="acme") as span:
        hits = do_lookup(name)
        span.set_attribute("agent.tool.result_count", len(hits))
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

# Attribute namespace for agent-step spans, kept distinct from the gateway's
# `llm.gateway.*` so a Phoenix filter can separate tool/step work from LLM work.
_NS = "agent"


class _NoopSpan:
    """Stand-in when tracing is unavailable — same surface, does nothing."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def is_recording(self) -> bool:
        return False


def _live_span():
    """The current OTel span if one is recording, else None."""
    try:
        from opentelemetry import trace
    except Exception:  # opentelemetry not installed
        return None
    span = trace.get_current_span()
    if span is None or not getattr(span, "is_recording", lambda: False)():
        return None
    return span


@contextmanager
def agent_span(
    name: str,
    *,
    tenant_id: Optional[str] = None,
    kind: str = "step",
    **attributes: Any,
) -> Iterator[Any]:
    """Open a child span for a tenant pipeline step.

    Records duration and any keyword attributes under `agent.*`; on an
    exception it stamps `agent.error` and re-raises (the step still fails —
    tracing only observes). No-ops cleanly without opentelemetry or an
    active tracer, so tenant code can wrap every step unconditionally.
    """
    tracer = None
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("agentsmith.runtime")
    except Exception:
        tracer = None

    start = time.perf_counter()
    if tracer is None:
        span: Any = _NoopSpan()
        _stamp(span, name, tenant_id, kind, attributes)
        try:
            yield span
        finally:
            pass
        return

    with tracer.start_as_current_span(f"{_NS}.{name}") as span:
        _stamp(span, name, tenant_id, kind, attributes)
        try:
            yield span
        except Exception as exc:
            try:
                span.set_attribute(f"{_NS}.error", type(exc).__name__)
                span.record_exception(exc)
            except Exception:  # fail-open: tracing must never mask the real error
                pass
            raise
        finally:
            try:
                span.set_attribute(
                    f"{_NS}.duration_ms", (time.perf_counter() - start) * 1000
                )
            except Exception:  # fail-open: never break the step on a tracing write
                pass


def _stamp(span: Any, name: str, tenant_id: Optional[str], kind: str, attrs: dict) -> None:
    try:
        span.set_attribute(f"{_NS}.step", name)
        span.set_attribute(f"{_NS}.kind", kind)
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)
        for k, v in attrs.items():
            if v is not None:
                span.set_attribute(f"{_NS}.{k}", v)
    except Exception:  # fail-open: attribute writes must never raise into the step
        pass


def record_tool_call(
    name: str,
    *,
    allowed: bool,
    duration_ms: float,
    error: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> None:
    """Emit a CHILD span for one tool invocation (`agent.tool.<name>`).

    Called from `ToolRegistry.invoke` so every tool call is visible in
    Phoenix — the allow/deny outcome, duration, and any error — which the
    'every tool call streamed' claim requires but nothing delivered.

    A child span rather than an annotation on the enclosing step, because a
    single step routinely calls several tools (sanctions + registry + media
    in one research step); annotating the current span would let each call
    clobber the previous one's `agent.tool.*` attributes and only the last
    would survive. Nested under the active `agent_span` when there is one,
    so the parent/child structure still shows which step made the call.
    """
    tracer = None
    try:
        from opentelemetry import trace

        if not getattr(trace.get_current_span(), "is_recording", lambda: False)():
            # No active recording span → creating a lone root span per tool
            # call would be noise; only trace tool calls inside a step.
            return
        tracer = trace.get_tracer("agentsmith.runtime")
    except Exception:
        return
    if tracer is None:
        return

    try:
        with tracer.start_as_current_span(f"{_NS}.tool.{name}") as span:
            span.set_attribute("agent.tool.name", name)
            span.set_attribute("agent.tool.allowed", allowed)
            span.set_attribute("agent.tool.duration_ms", duration_ms)
            if tenant_id:
                span.set_attribute("tenant.id", tenant_id)
            if error:
                span.set_attribute("agent.tool.error", error)
    except Exception:  # fail-open: tracing must never break a tool call
        pass
