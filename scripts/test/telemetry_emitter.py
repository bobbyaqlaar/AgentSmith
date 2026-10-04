"""
scripts/test/telemetry_emitter.py — one representative run through AgentSmith's
runtime library, for the telemetry contract (contract/telemetry/v1).

    python scripts/test/telemetry_emitter.py           export over OTLP, as configured by
                                                      the OTEL_EXPORTER_OTLP_* variables
    representative_run()                              the same run, in-process

What `agentsmith conformance --port telemetry --emitter` scores the library with,
and what `contract/telemetry/v1/fixture.json` was generated from: a step, a tool
call inside it, an LLM call with reported usage and a retrieval — each inside a
run — and the metrics they record. Real code paths only: the gateway's own span,
the identity processor, the vector store.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

TENANT = "fixture-tenant"
RUN = "run-0001"


def representative_run() -> None:
    """Emit the run through whatever providers are installed."""
    os.environ.setdefault("IDEMPOTENCY_BACKEND", "memory")
    os.environ.setdefault("BUDGET_BACKEND", "memory")
    from runtime.llm_gateway import LLMGateway
    from runtime.tenancy import agent_context
    from runtime.tracing import agent_span, record_tool_call
    from runtime.vector_store import MemoryVectorStore

    gateway = LLMGateway(tenant_id=TENANT)
    store = MemoryVectorStore(embedder=_Embedder())
    with agent_context(role="analyst", tenant_id=TENANT, run_id=RUN):
        with agent_span("analyse", kind="step", case="c-1"):
            record_tool_call("sanctions_lookup", allowed=True, duration_ms=12.5, tenant_id=TENANT)
            store.add(["doc-1", "doc-2"], ["a sanctions list entry", "a news article"])
            store.query("sanctions", k=2)
        # Outside the step: the gateway opens its own `llm.<role>` span.
        gateway._record_span_attributes(
            "analyst", "claude-sonnet-5-5", None, "wf-1", 0.0123, 410.0,
            input_tokens=1500, output_tokens=270, started_ns=time.time_ns() - 900_000_000,
            outcome="ok",
        )


class _Embedder:
    """Two dimensions, deterministic — the store needs one, the run does not care which."""

    identity = "fixture-embedder"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 7), 1.0] for t in texts]


def main() -> int:
    from runtime.tracing import configure_telemetry

    providers = configure_telemetry(project_name=TENANT, metrics_interval_ms=1_000)
    representative_run()
    for provider in providers.values():
        if provider is not None and hasattr(provider, "shutdown"):
            provider.shutdown()  # flushes: a short-lived process otherwise drops its batch
    return 0


if __name__ == "__main__":
    sys.exit(main())
