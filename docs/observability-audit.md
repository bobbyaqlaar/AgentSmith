# Observability audit — what AgentSmith emits, and what it does not

**Audited:** 2026-08-24, against `runtime/`, `portal/`, and `templates/agent-rules.yaml` pillar 3.
**Scope:** the production runtime a tenant executes. Where the demo scripts differ, it is called out — the difference is itself a finding.

This is a gap register, not a design doc. Every ❌ is a claim the framework does not currently support; every ⚠️ is one it supports conditionally, with the condition stated. Items fixed during the audit are marked ✅ **fixed** with the commit rationale.

---

## 1. The pillar 3 claim

> *Every span must carry: `agent.name`, `agent.role`, `agent.owner_id`, `tenant.id`, `llm.model_name`, `project.name`, `environment`.*

**This is not enforced, and half of it is not implemented in the runtime at all.**

| Attribute | Production runtime | Demo scripts | Enforced? |
|---|---|---|---|
| `tenant.id` | ⚠️ conditional | ✅ | ❌ |
| `llm.model_name` | ✅ on gateway calls | ✅ | ❌ |
| `agent.role` | ❌ never written | ✅ per span, by hand | ❌ |
| `agent.name` | ❌ never written | ✅ | ❌ |
| `agent.owner_id` | ❌ never written | ✅ | ❌ |
| `project.name` | ❌ never written | ✅ resource + root span | ❌ |
| `environment` | ❌ never written | ⚠️ resource only | ❌ |

`agent.role`, `agent.name`, `agent.owner_id` and `project.name` appear **only** in
`scripts/local_agent_stack.py` and `scripts/multi_agent_system.py` — the demo and dev
harnesses — set by hand on each span. `runtime/tracing.py` and `runtime/llm_gateway.py`,
which is what tenants actually run, never write them.

`tenant.id` is conditional: `runtime/tracing.py`'s `_stamp` writes it under `if tenant_id:`.
Omit the kwarg and the span has no tenant, with no error and no warning. Same in
`record_tool_call`.

**Nothing enforces the contract.** No span processor injects the attributes; no test asserts
callers supply them. `runtime/test/test_tracing.py` asserts `tenant.id == "acme"` *when it was
passed* — that tests the helper, not the pillar. Pillar 3 is in the same position the `SEC-*`
controls were in before their runners were bound: a documented claim with nothing checking it.

### Recommendation — make it structural, not disciplinary

Split the attributes by how they vary:

- **Static per process** (`agent.role` where a worker serves one role, `project.name`,
  `service.name`, `environment`, `agent.owner_id`) → the OTel **Resource**. Set once at
  provider construction; every span inherits it and no call site can omit it.
- **Dynamic per request** (`tenant.id`, `run_id`, and `agent.role` where one worker serves
  several) → a **contextvar** stamped by an `on_start` SpanProcessor.

Then an unattributed span is structurally impossible rather than a rule forty call sites must
remember. Add a test that runs a representative workflow and asserts **no emitted span** is
missing the required set — that is the runner pillar 3 currently lacks.

**Open question before implementing:** is `agent.role` per-process or per-step in your
deployment? A worker serving a single role makes it a Resource attribute; a worker
multiplexing roles makes it context. The answer changes the design.

---

## 2. User request logging

| Item | Status | Where |
|---|---|---|
| Request ID | ⚠️ `agent_runs.run_id` per gateway call; no ID crossing service boundaries | `llm_gateway.py` |
| Session ID | ❌ no concept | — |
| User query | ⚠️ deliberate — scrubbed by profile | `trace_redactor.py` |
| Timestamp | ✅ `started_at` / `finished_at` | `agent_runs` |
| Model used | ✅ `llm.model_name` | span |
| Token usage | ✅ **fixed** — see below | span + `agent_runs` |
| Latency | ✅ `agent.duration_ms`, run duration | span, `agent_runs` |
| Response status | ✅ `running` / `success` / `degraded` / `failed` | `agent_runs` |

### ✅ Fixed: token usage was computed and discarded

`CompletionResult` has carried `input_tokens` / `output_tokens` since the gateway was written,
and **not one of the four references reached a span or a database column**. Cost could be
charted but never attributed to a prompt: you could see spend rise and not see which call
caused it.

Now on the span as `llm.usage.input_tokens` / `output_tokens` / `total_tokens`, and persisted
to `agent_runs.input_tokens` / `output_tokens` / `cost_usd`.

**The nullability is the point.** A streamed call reports no usage in v1 and the result
carries `0/0` for it. Writing that `0` would make *"used no tokens"* and *"nobody counted"*
the same number on any dashboard that sums them — undercounting every streamed run while
looking complete. So:

- the span carries `llm.usage.reported` (bool) and omits the token attributes when false;
- the columns are **nullable**, and the ingest route coerces non-numeric input to `NULL`
  rather than `0`;
- the upsert `COALESCE`s, so the run-start write (no usage yet) and a later heartbeat cannot
  blank a figure already recorded.

Also added: `llm.gateway.cost_estimated`. The streamed path bills the `try_reserve()` figure
derived from `max_tokens` — a ceiling, not a measurement — and an estimate must not read like
one.

### Remaining gaps

**Session ID and a cross-service request ID.** `run_id` is per gateway call. There is no
identifier that survives User → API → worker → portal, so you cannot reconstruct one user
interaction that spanned several calls. This is the same gap as §5.

**User query.** Deliberately absent by default; `trace_redactor` scrubs free text by
`ENVIRONMENT` profile, with a HITL escrow that keeps the full payload for flagged production
spans. That is the right default for a PDPL/GDPR posture. Recommendation: keep it, and
document the escrow as the sanctioned path rather than letting tenants disable redaction to
debug.

---

## 3. Prompt & context logging

**The weakest category, and the one where degradation root-causes actually live.**

| Item | Status |
|---|---|
| System prompt version | ❌ **not implementable today** |
| Prompt template version | ❌ same |
| User prompt | ⚠️ redacted by profile; escrowed for HITL-flagged spans |
| Retrieved RAG chunks | ❌ only `agent.tool.result_count` — a count, not identities |
| Conversation history | ❌ `conversation_memory` is untraced |
| Tool outputs | ❌ `record_tool_call` records name / allowed / duration / error only |

`FIXES_AND_CLEANUP.md` already records that there is no prompt-template engine and that
prompts are inline f-strings. So there is **no version to log** — the gap is upstream of
observability.

### Recommendation — hash first, engine later

Do not wait for the template engine. Emit `prompt.template.id` (a stable name chosen at the
call site) and `prompt.template.sha256` (of the template *before* interpolation). That gives
you "answers degraded when this hash changed" for near-zero cost, works with inline f-strings
today, and survives the eventual move to a real engine unchanged.

For retrieval, a count is not evidence. `agent.tool.result_count = 3` tells you nothing when
the wrong three came back. Emit chunk **ids and scores** — that is what distinguishes "the
retriever failed" from "the model ignored good context", which is the single most common
question asked of a RAG system.

---

## 4. Agent & tool tracing

| Item | Status |
|---|---|
| Which tool was called | ✅ child span per call, nested under the step |
| Execution time | ✅ `agent.tool.duration_ms` |
| Errors | ✅ `agent.tool.error` |
| Allow/deny outcome | ✅ `agent.tool.allowed` |
| Input / output | ❌ |
| Retry attempts | ❌ |
| Decision path | ⚠️ `llm.gateway.degrade_reason` only |

`record_tool_call` is genuinely good on the security axis: recording the **allow/deny
outcome** of an allowlist check is rare and it makes `SEC-TOOL-001` observable rather than
merely asserted.

### Recommendation — retries first

The gateway retries provider 429s with full-jitter backoff, and **nothing on the span says an
attempt happened**. A call retried three times looks like a slow call. On free-tier judges
where 429s are routine, that is actively misleading: you would tune latency when the problem
is quota. Emit `llm.gateway.attempts` and a span event per retry with the provider's message.

Tool input/output is second. Redaction applies — route it through `trace_redactor` the same
way prompts are, rather than adding an unscrubbed channel.

---

## 5. Model performance metrics

| Item | Status |
|---|---|
| Prompt latency / total response time | ✅ span durations |
| First-token latency | ⚠️ `llm.gateway.ttft_ms`, **stream path only** |
| Input / output tokens | ✅ **fixed** (§2) |
| Cost per request | ✅ `llm.gateway.cost_usd`, now flagged when estimated |
| Error rate | ⚠️ derivable from spans; no counter |
| Hallucination feedback | ⚠️ offline only — the eval suites; shadow-eval samples spans |
| Cache hit ratio | ❌ hit/miss is **logged**, never an attribute or metric |

TTFT on the non-stream path is unmeasurable without a synthetic first token and is already
documented as such — that one is honest.

### Recommendation — the missing instrument is metrics

**There are no OTel Metrics anywhere in this codebase.** Everything is spans. Computing rates
and ratios by scanning spans is expensive, sampling-sensitive, and degrades as volume grows —
and error rate, cache hit ratio and p95 TTFT are exactly the numbers you want on a dashboard
refreshing every fifteen seconds.

Add a meter alongside the tracer: counters for calls / errors / cache hits, a histogram for
TTFT and total duration. The idempotency cache already knows its hit/miss at
`llm_gateway.py` — it just logs it. That is one counter away from being a real ratio.

---

## 6. Distributed tracing

**This is the largest structural gap.** There is **no context propagation in the codebase** —
no `inject`, no `extract`, no `traceparent` anywhere.

For the chain your architecture implies:

```
User → API → Orchestrator → Vector DB → Embedding → LLM → Database
```

only the LLM hop is instrumented, and until this audit it was stitched to its parent **only
when the tenant remembered to wrap the call**. The worker's run-status POST to the portal
carries no trace context, so the portal's work is a *separate trace*. `agent_runs.trace_id` is
a manual correlation column, not W3C propagation. `vector_store.query` and `embeddings` emit
no spans at all.

### ✅ Partially fixed: an LLM call is no longer absent from the trace

`_record_span_attributes` wrote onto `trace.get_current_span()` behind `if span is None:
return`. `get_current_span()` **never returns None** — with nothing active it returns a
`NonRecordingSpan` whose `set_attribute` is a silent no-op. So the guard never fired, and on
any path not already inside an `agent_span` the entire LLM call vanished from the trace:
model, cost, tokens, latency, all dropped without a signal.

Worth stating precisely, because it shaped the fix: **repairing the guard alone would have
changed nothing** — a no-op write and an early return lose the attributes equally. What
changes it is the fallback. With no parent span the gateway now emits its own `llm.<role>`
span, created with the real `start_time` so its duration is honest. Without a start time it
declines to invent one: a span reading as instantaneous is worse than an absent one, because
it drags every latency percentile computed from it toward zero.

`record_tool_call` deliberately declines to emit lone root spans, and that remains correct —
a step makes several tool calls and orphan roots would be noise. An LLM call is the opposite
case: one per step, and the unit every dashboard is keyed on.

### Recommendation — propagation is the cheapest high-value work left

1. `inject` trace context into the run-status POST headers; `extract` in the portal route.
   Two small changes, and the portal stops being a separate trace.
2. Span `vector_store.query` and the embedding call. Both are latency suspects and neither is
   visible.
3. Only then consider a collector fan-out (Phoenix for LLM semantics, Tempo/Jaeger for
   infra-grade search). Propagation first — fan-out multiplies traces, and multiplying broken
   traces does not help.

---

## 7. Tooling posture

You are OTel-native with Phoenix, and that is the right spine.

| Tool | Verdict |
|---|---|
| **OpenTelemetry** | ✅ keep as the wire format. Everything below should feed it, not replace it. |
| **Phoenix (Arize)** | ✅ right for eval, hallucination analysis and trace inspection. The shadow-eval loop already feeds it. |
| **LangSmith / Langfuse** | ⚠️ not recommended *alongside* OTel. Both bring their own span models; adopting one means two vocabularies and a lossy bridge. Choose them instead of OTel or not at all. |
| **MLflow Tracing** | ⚠️ overlaps Phoenix. No reason to run both. |
| **Prometheus / Grafana** | ✅ **the actual gap** — nothing in the current stack covers metrics (§5). |
| **Datadog / Azure Monitor** | ⚠️ viable as an OTLP sink if the org already pays for one; not a second instrumentation. |
| **Jaeger / Tempo** | ⚠️ only after §6 propagation exists, and via collector fan-out rather than double instrumentation. |

---

## Priority

1. **Enforce pillar 3** via Resource + `on_start` processor, with a test asserting no span is
   missing the required set. Everything else is unreliable until identity is. *(Blocked on the
   per-process vs per-step question above.)*
2. ~~Fix the dead span guard~~ ✅ done — and the fallback that makes it matter.
3. ~~Token capture~~ ✅ done, span and database, with "not measured" preserved.
4. **Context propagation** — `inject` on the ingest POST; spans on vector store and embeddings.
5. **Prompt hash** — cheap root-cause for degradation, no template engine required.
6. **OTel Metrics** — counters and histograms for the rates and ratios.
7. **Retry visibility** — `llm.gateway.attempts` plus a span event per retry.

---

*Fixed items are covered by `runtime/test/test_gateway_span_usage.py` (span attributes,
including that unreported usage is absent rather than zero) and
`portal/test/agentRuns.test.ts` (persistence, including that a later write carrying no usage
does not blank a recorded figure). Both run in CI.*
