# Observability audit — what AgentSmith emits, and what it does not

**Audited:** 2026-08-24, against `runtime/`, `portal/`, and `templates/agent-rules.yaml` pillar 3.
**Scope:** the production runtime a tenant executes. Where the demo scripts differ, it is called out — the difference is itself a finding.

This is a gap register, not a design doc. Every ❌ is a claim the framework does not currently support; every ⚠️ is one it supports conditionally, with the condition stated. Items fixed during the audit are marked ✅ **fixed** with the commit rationale.

---

## 1. The pillar 3 claim

> *Every span must carry: `agent.name`, `agent.role`, `agent.owner_id`, `tenant.id`, `llm.model_name`, `project.name`, `environment`.*

✅ **Fixed 2026-08-24.** It was not enforced, and half of it was not implemented in
the runtime at all. The table below is the audited state; what replaced it follows.

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

### ✅ Fixed — made structural, not disciplinary

The attributes are split by how they actually vary:

- **Per-process → OTel `Resource`** (`runtime/tracing.py:resource_attributes`):
  `service.name`, `project.name`, `environment`, `agent.owner_id`. Fixed at provider
  construction; every span inherits them and no call site can omit one.
- **Per-step → contextvars + `AgentIdentityProcessor.on_start`**
  (`runtime/tenancy.py`): `tenant.id`, `agent.role`, `run.id`. Bound once at the
  activity boundary; every span started inside — including the gateway's and
  `ToolRegistry`'s — is stamped without anyone passing a kwarg.

`agent.role` **cannot** be a Resource attribute here, and that is the finding rather
than a detail. KYC's worker registers six activities on one task queue, and the
framework's reference worker three; a Resource would stamp every span with one role,
making five of six confident lies. An absent attribute is a gap you can see in a
query — a wrong one is aggregated with real data.

`tenant.id` cannot be one either, for a subtler reason: KYC is `isolation: dedicated`
so it *is* constant per process there, but the framework default is a shared pool
partitioned by tenant (SPECS.md §23). A Resource attribute would be correct for the
tenant it was built against and silently wrong for every other — which is the
failure mode this framework has already had once, when the security harness graded
its own pack.

**Resolution.** `tenant.yaml` had declared `tenant.id` since the scaffold shipped and
nothing read it — `llm_gateway.py` opens that exact file for
`gateway.routing_overrides` and walked past the id. So callers supplied their own, and
KYC Sentinel ended up with the value in **four** places: two in `agents/gateway.py`,
one as a `getattr` fallback in `pipeline.py`, one in `agents/tools.py`.
`runtime/tenancy.py:resolve_tenant_id()` reads the declaration — explicit argument →
`AGENT_TENANT_ID` → `tenant.yaml` → **raise**. All four copies are deleted.

The refusal is deliberate. `tenant.id` partitions the budget ledger, the audit log and
cross-tenant isolation; an unresolved tenant quietly becoming `unknown` would merge two
tenants' spend and two tenants' audit trail and look fine doing it.

**Not derived from the repo name**, though it was considered and would have worked
here: KYC is single-tenant so its tenant equals its repo. On the shared-pool default
one repo serves many tenants, so a repo-derived id would collapse them; production
containers have no `.git` and no `GITHUB_REPOSITORY`, so it would resolve in CI and
fall back exactly where the audit trail matters; and it would make a compliance
identifier mutable by renaming a directory. The repo name *is* the right default for
`project.name`, where nothing partitions on it — that is where it now lives.

**The runner.** `runtime/test/test_pillar3_conformance.py` asserts the property over
**emitted spans**, not over the helper that emits them. That distinction is what let
the old assertion pass while the contract was broken: it checked `tenant.id == "acme"`
on a call that had just passed `tenant_id="acme"`.

**And the tenant now has tracing at all.** KYC installed no `TracerProvider`, so every
`agent_span()` in the framework's own E2E testbed was a no-op and no span had ever
reached Phoenix from it. `configure_tracing()` is one call that assembles Resource,
identity processor, redactor and exporter; `worker.py` calls it. A documented
three-step recipe had produced zero correct setups.

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
| System prompt version | ✅ **fixed** — `prompt.system.sha256` |
| Prompt template version | ✅ **fixed** — `prompt.template.id`, chosen at the call site |
| User prompt | ⚠️ redacted by profile; escrowed for HITL-flagged spans |
| Retrieved RAG chunks | ✅ **fixed** — ids and scores, see §6 |
| Conversation history | ❌ `conversation_memory` is untraced |
| Tool outputs | ❌ `record_tool_call` records name / allowed / duration / error only |

`FIXES_AND_CLEANUP.md` already records that there is no prompt-template engine and that
prompts are inline f-strings. So there is **no version to log** — the gap is upstream of
observability.

### ✅ Fixed — hash first, engine later

`runtime/prompt_identity.py` emits `prompt.system.sha256`, `prompt.system.chars`,
`prompt.template.id` and `prompt.message_count`, stamped by the gateway's
`_stamp_llm_span`. The digest is of the system turn, so it changes when and only
when a human edits the prompt; the text itself is never recorded. The redactor
lists `prompt.system.sha256` as untruncatable — a truncated digest silently stops
joining, which is worse than an absent one.

The recommendation as written, kept because it is the reasoning the fix was
built on:

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
| Retry attempts | ✅ **fixed** |
| Decision path | ⚠️ `llm.gateway.degrade_reason` only |

`record_tool_call` is genuinely good on the security axis: recording the **allow/deny
outcome** of an allowlist check is rare and it makes `SEC-TOOL-001` observable rather than
merely asserted.

### ✅ Fixed — retries are visible

`llm.gateway.attempts` on every call — recorded as 1 when there was no retry, so "this call
did not retry" is a fact rather than the absence of one. A `llm.retry` span **event** per
attempt carries the attempt number, the sleep, and the provider's actual message; a
`agentsmith.llm.retries` counter carries a COARSE reason (`rate_limit`, `timeout`,
`server_error`, `transient`) because a metric attribute holding free text creates a time
series per distinct string.

Driven through tenacity itself in the test rather than a stand-in, so the wiring —
`before_sleep`, the statistics dict, the attribute name — is what is verified.

**Still open:** tool input/output. Redaction applies, so it should route through
`trace_redactor` the same way prompts do rather than adding an unscrubbed channel.

---

## 5. Model performance metrics

| Item | Status |
|---|---|
| Prompt latency / total response time | ✅ span durations |
| First-token latency | ⚠️ `llm.gateway.ttft_ms`, **stream path only** |
| Input / output tokens | ✅ **fixed** (§2) |
| Cost per request | ✅ `llm.gateway.cost_usd`, now flagged when estimated |
| Error rate | ✅ **fixed** — `agentsmith.llm.calls` with an `outcome` dimension |
| Hallucination feedback | ⚠️ offline only — the eval suites; shadow-eval samples spans |
| Cache hit ratio | ✅ **fixed** — `agentsmith.llm.cache` with a `hit` dimension |

TTFT on the non-stream path is unmeasurable without a synthetic first token and is already
documented as such — that one is honest.

### ✅ Fixed — a meter alongside the tracer

`runtime/metrics.py`. Counters for calls, cache hit/miss and cost; histograms for duration,
TTFT and token counts. Both, not either: spans answer "what happened in this request", and
they are the wrong instrument for "what fraction of requests failed" — that answer is
sampled, expensive to scan, and gets worse as traffic grows. `outcome` is a dimension on the
call counter, so the error rate is a division rather than a scan.

The cache hit ratio was the clearest case: the gateway already knew whether it hit and only
logged it, so no backend could compute the ratio at all.

`configure_metrics()` is separate from `configure_tracing()` on purpose — a deployment can
reasonably want metrics to Prometheus and traces to Phoenix, and coupling them would force
both or neither.

### ⚠️ → ✅ The correction: none of the above was reaching anything

**Found 2026-08-25.** The section above was true about the instruments and wrong about the
system. `configure_metrics()` **had no caller anywhere** — not `runtime/worker.py`, not KYC
Sentinel's worker, not `examples/oil-price-agent`. Its only three mentions in the repo were
its own definition, its own docstring, and the paragraph immediately above this one.

With no MeterProvider installed, `opentelemetry.metrics.get_meter()` returns a `_ProxyMeter`
whose instruments buffer for a real provider that never arrives. Nothing raises and nothing
logs. So every correctly-placed, correctly-attributed `record_llm_call`, `record_cache`,
`record_retry` and `record_retrieval` wrote into nothing, and the four numbers this section
exists to deliver were computable nowhere — while the section read ✅.

`runtime/test/test_metrics.py` was green throughout because it installs its own
`MeterProvider` and `InMemoryMetricReader` in a fixture. It proves the instruments record
**when a provider exists**; nothing proved one ever did. That is the same pairing that let
pillar 3 pass while unenforced (§1) — a control with no enforcer, and a test of the helper
rather than the contract.

**Fixed:** `configure_telemetry()` installs both providers in one call, with exporters
resolved from the environment, and `runtime/worker.py`, the example worker and KYC's worker
all call it. `runtime/test/test_telemetry_wiring.py` asserts in a **subprocess** that a fresh
process ends up with a real SDK meter and non-proxy instruments — plus a control test that
the same process WITHOUT the call gets proxies, so the assertion is not free — and sweeps
every worker entrypoint for the call itself, because the defect was an absent call rather
than wrong code.

### ✅ Fixed — one OTLP endpoint resolver, not four

Wiring metrics surfaced a second thing. Four places turned an endpoint variable into an OTLP
URL — `scripts/local_agent_stack.py`, `scripts/multi_agent_system.py`, KYC's `worker.py` and
`portal/lib/tracing.ts` — and only the last was correct. Every Python copy ended
`f"{endpoint.rstrip('/')}/v1/traces"`; the portal's detects a base that already names the path,
because this repo's own convention (OPERATIONS.md, `docker-compose.yml`, SPECS.md §699,
`ai-dashboard-start`) puts a full `…/v1/traces` URL in the variable the OTLP spec defines as a
base. `local_agent_stack.py` falls back to exactly that variable and appended anyway.

The guard was written once, in TypeScript, and the Python sibling reading the same variable in
the same repo never got it — the "fix applied at one call site and not its identical
neighbours" shape, across a language boundary.

`runtime/otlp.py` is the one copy now, ported from the portal's rather than invented fifth. It
also handles a case the portal's could not have: a base naming a DIFFERENT signal, which must
not yield `/v1/traces/v1/metrics`. `portal/lib/tracing.ts` cannot import Python, so the two are
**pinned** by a test that parses the TypeScript for its variable order and its suffix guard
rather than restating them.

---

## 6. Distributed tracing

✅ **Partially fixed 2026-08-25.** It was the largest structural gap: no `inject`,
no `extract`, no `traceparent` anywhere in the codebase.

For the chain your architecture implies:

```
User → API → Orchestrator → Vector DB → Embedding → LLM → Database
```

only the LLM hop is instrumented, and until this audit it was stitched to its parent **only
when the tenant remembered to wrap the call**. The worker's run-status POST to the portal
carries no trace context, so the portal's work is a *separate trace*. `agent_runs.trace_id` is
a manual correlation column, not W3C propagation. `vector_store.query` and `embeddings` emit
no spans at all.

*(All four are now closed — see the two fixed sections below. The paragraph above is left as
written because it is the finding, and a finding that is quietly edited into its own fix
stops being evidence of anything.)*

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

### ✅ Fixed — the request now survives the process hop

1. **`traceparent` on the run-status POST.** `runtime/tracing.inject_context()` adds the W3C
   header to the worker's call, and `/api/runs/ingest` parses it by hand. That hand parser is
   kept now that the portal *is* instrumented, because it is the one path that still works
   with tracing switched off. An all-zero trace id is the invalid one the spec reserves and is
   rejected rather than stored.
2. **`agent_runs.trace_id` is populated.** It was NULL for every run ever recorded:
   `_report_run_status` accepted a `trace_id` argument that not one of its nine call sites
   passed, so the portal's trace link had nothing to link to. It defaults to the active trace.
3. **The retrieval hop emits spans.** `vector_store.query` (both backends) and the
   sentence-transformers `embed` were entirely invisible, so "the retriever was slow" and
   "the model was slow" were the same picture. Spans carry hit **identities and scores**, not
   just `result_count` — a count of 3 says nothing when the wrong three came back, which is
   the most common question asked of a RAG system. Retrieved TEXT is deliberately excluded:
   it is the likeliest place for PII to enter a span and the redactor runs later.

### ✅ Fixed — the portal is in the trace, not merely linked from it

The last open item. `agent_runs.trace_id` let a portal row link *to* a trace; the portal's own
work — three Postgres round-trips per ingest, an outbound Phoenix query that can hang for the
full five seconds its `AbortSignal` allows — appeared in no trace at all, including the one it
was serving.

`portal/instrumentation.ts` registers a provider, and that single act does more than add the
spans below: Next.js instruments its own request handling only when a provider is registered,
and it calls `propagation.extract` on the incoming headers before the handler runs. So the
worker's `traceparent` becomes the **parent** of the portal's request span rather than a
string copied into a column.

Verified against a running build rather than asserted — a worker's header in, the exported
OTLP payload out:

```
POST /api/runs/ingest/route   trace=99887766…eeff  parent=1122334455667788   ← the worker's span
  portal.runs.ingest          trace=99887766…eeff  tenant.id=span-proof-3
  portal.db.SELECT            trace=99887766…eeff  tenant.id=span-proof-3
  portal.db.INSERT            trace=99887766…eeff  tenant.id=span-proof-3
```

What that run changed: the first version bound the tenant one block too late, and the trace
showed the SELECT that looks a tenant up and the INSERT that creates it exporting with **no
`tenant.id`** — the two spans that are entirely about a tenant. Identity is now bound at the
first line that knows one.

- **Every query is traced, without a call site opting in.** `lib/db.ts` returns a pool whose
  `query` opens a span, rather than a helper the twenty-eight existing call sites would each
  have to remember. `db.statement` carries the *parameterised* text — code, not data — and the
  values are never recorded: unlike the worker's spans, nothing redacts a portal span. The
  callback and Cursor forms of `pg.query` return something other than a promise and are passed
  straight through untraced, rather than silently changing what a caller gets back.
- **Pillar 3 holds on the portal too**, split the same way: `service.name`, `project.name`,
  `environment` and `agent.role: ops-portal` on the Resource; `tenant.id` and
  `portal.actor.role` stamped per span by `PortalIdentityProcessor` from the active context.
  `portal.actor.role` is the human's RBAC role and is deliberately *not* called `agent.role` —
  an operator is not an agent, and one attribute meaning two things is pillar 15.
- **An operator action is attributable.** `portal.dlq.replay` and `portal.dlq.discard` record
  which role acted on which entry. The replayed payload is not recorded: it is operator-edited
  tenant data on its way to a tenant's webhook.
- **The endpoint trap.** This repo's own convention sets `OTEL_EXPORTER_OTLP_ENDPOINT` to a
  full `…/v1/traces` URL — fine for the Python exporter, which is handed it directly. The JS
  exporter appends `/v1/traces` to what it is given, so the same value everything else here
  uses would have POSTed to `/v1/traces/v1/traces` and dropped every span on a 404 that
  surfaces nowhere. `resolveTracesEndpoint()` detects the suffix instead of assuming it.

**Still open:** a collector fan-out (Phoenix for LLM semantics, Tempo/Jaeger for infra search)
is now possible but not configured — both sides currently export to one endpoint.

---

## 7. Tooling posture

You are OTel-native with Phoenix, and that is the right spine.

| Tool | Verdict |
|---|---|
| **OpenTelemetry** | ✅ keep as the wire format. Everything below should feed it, not replace it. |
| **Phoenix (Arize)** | ✅ right for eval, hallucination analysis and trace inspection. The shadow-eval loop already feeds it. |
| **LangSmith / Langfuse** | ⚠️ not recommended *alongside* OTel. Both bring their own span models; adopting one means two vocabularies and a lossy bridge. Choose them instead of OTel or not at all. |
| **MLflow Tracing** | ⚠️ overlaps Phoenix. No reason to run both. |
| **Prometheus / Grafana** | ✅ metrics now exist AND are exported — `configure_telemetry()` installs a MeterProvider and resolves `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`. Point it at a collector that fans out to Prometheus; no second instrumentation. |
| **Datadog / Azure Monitor** | ⚠️ viable as an OTLP sink if the org already pays for one; not a second instrumentation. |
| **Jaeger / Tempo** | ⚠️ only after §6 propagation exists, and via collector fan-out rather than double instrumentation. |

---

## Priority

1. ~~Enforce pillar 3~~ ✅ done — Resource + `on_start` processor, `resolve_tenant_id()`,
   a conformance test over emitted spans, and a tenant that installs tracing at all.
2. ~~Fix the dead span guard~~ ✅ done — and the fallback that makes it matter.
3. ~~Token capture~~ ✅ done, span and database, with "not measured" preserved.
4. ~~Context propagation~~ ✅ done — `traceparent` injected and parsed, `trace_id`
   populated, retrieval and embedding spans emitted.
5. ~~Prompt hash~~ ✅ done — `prompt.system.sha256`, `prompt.template.id`,
   `prompt.system.chars`, `prompt.message_count`, with the digest untruncatable.
6. ~~OTel Metrics~~ ✅ done — counters and histograms for the rates and ratios, **and a
   provider that makes them leave the process.** The instruments landed first and were
   proxied into nothing for as long as no entrypoint called `configure_metrics()`; see the
   correction in §5. One `configure_telemetry()` installs both signals, and one
   `runtime/otlp.py` resolves both endpoints for all four callers that used to do it
   separately.
7. ~~Retry visibility~~ ✅ done — `llm.gateway.attempts`, a span event per retry carrying the
   provider's message, and a counter with a bounded reason.

---

*Fixed items are covered by `runtime/test/test_gateway_span_usage.py` (span attributes,
including that unreported usage is absent rather than zero),
`portal/test/agentRuns.test.ts` (persistence, including that a later write carrying no usage
does not blank a recorded figure), `runtime/test/test_pillar3_conformance.py` (§1, asserted
over emitted spans rather than the helper), `runtime/test/test_telemetry_wiring.py` (§5, that
a fresh process ends up with a real meter and not a proxy) and
`runtime/test/test_otlp_endpoint.py` (the single endpoint resolver, pinned against the
TypeScript copy it cannot import). All run in CI.*
