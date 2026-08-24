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
from pathlib import Path
from typing import Any, Iterator, Optional

# Attribute namespace for agent-step spans, kept distinct from the gateway's
# `llm.gateway.*` so a Phoenix filter can separate tool/step work from LLM work.
_NS = "agent"


def _repo_root() -> Path:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    return cwd


class _NoopSpan:
    """Stand-in when tracing is unavailable — same surface, does nothing."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401
        return None

    def record_exception(self, exc: BaseException) -> None:
        return None

    def is_recording(self) -> bool:
        return False


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


# ── Identity: Resource + on_start stamping (pillar 3) ────────────────────────


def resource_attributes(project_name: Optional[str] = None) -> dict:
    """The PER-PROCESS half of pillar 3 — fixed for the life of the worker.

    These four cannot vary between two spans from the same process, so they
    belong on the OTel Resource where every span inherits them and no call site
    can forget one. `agent.role` and `tenant.id` are deliberately absent: this
    architecture runs many roles in one worker (KYC registers six activities on
    one task queue), and the shared-pool default serves many tenants from one
    process, so either as a Resource attribute would be a confident lie on most
    spans rather than a missing one.

    `project.name` is the one place a repo-derived default is right: it names
    the codebase, nothing partitions on it, and being wrong is cosmetic.
    """
    from runtime.environment import get_environment

    from runtime.config import resolve

    project = resolve(
        "tenant.name",
        explicit=project_name,
        env_var="AGENT_PROJECT_NAME",
        default=None,
    ) or _repo_root().name
    attrs = {
        "service.name": project,
        "project.name": project,
        "environment": get_environment(),
    }
    # `tenant.owner` is declared in tenant.yaml and was read by nothing, while
    # this attribute came from a shell profile — so on a dev machine every repo
    # reported the same owner and in CI none did. Env still wins as the
    # per-deploy override; the declaration is the default it falls back to.
    from runtime.config import resolve

    owner = resolve("tenant.owner", env_var="AGENT_OWNER_ID", default=None)
    if owner:
        # Omitted when unset rather than "unknown" — see current_identity().
        attrs["agent.owner_id"] = str(owner)
    return attrs


try:
    from opentelemetry.sdk.trace import SpanProcessor as _OTelSpanProcessor
except ImportError:  # tracing is optional
    _OTelSpanProcessor = object  # type: ignore


class AgentIdentityProcessor(_OTelSpanProcessor):
    """Stamps the PER-STEP half of pillar 3 onto every span, at start.

    Subclasses the SDK's SpanProcessor rather than duck-typing it. A plain
    class with on_start/on_end/shutdown/force_flush looks complete and is not:
    the SDK also calls a private `_on_ending`, so a duck-typed processor raises
    AttributeError on the FIRST span it sees. Same choice trace_redactor.py
    made, and for the same reason.

    `on_start` rather than `on_end`: an exporter may sample or drop on the
    attributes, and a span that gains its tenant only at the end has already
    been routed without it.

    This is what makes "every span carries tenant.id" true by construction
    instead of by discipline. It was previously a kwarg on `agent_span()`
    applied under `if tenant_id:` — so a caller who omitted it produced an
    unattributed span, silently, and most callers did.
    """

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        try:
            from runtime.tenancy import current_identity

            for key, value in current_identity().items():
                span.set_attribute(key, value)
        except Exception:  # fail-open: identity must never break a span
            pass

    # on_end / shutdown / force_flush come from the base class — this
    # processor only ever writes at start.


def configure_tracing(
    *,
    project_name: Optional[str] = None,
    exporter: Any = None,
    redact: bool = True,
) -> Any:
    """Install a TracerProvider wired the way pillar 3 requires. Returns it.

    Exists because assembling this by hand is three steps that must all be
    remembered, and the evidence says they are not: KYC Sentinel — the tenant
    built to exercise every layer of this framework — installs NO provider at
    all, so every `agent_span()` in it is a no-op and no span has ever reached
    Phoenix from it. A documented three-step recipe produced zero correct
    setups; a function is harder to half-do.

    Idempotent-ish: OTel's global provider is one-shot, so a second call is
    ignored by the SDK. Returns whatever provider is active either way.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError:  # fail-open: tracing is optional, the app is not
        return None

    provider = TracerProvider(resource=Resource.create(resource_attributes(project_name)))
    provider.add_span_processor(AgentIdentityProcessor())

    if redact:
        # Ordering matters: identity stamps at start, redaction rewrites at end.
        from runtime.trace_redactor import TraceRedactor

        provider.add_span_processor(TraceRedactor())

    if exporter is not None:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return trace.get_tracer_provider()
