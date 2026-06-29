# AgentSmith — Active Work and Future Phases

**Last reviewed:** 2026-06-30  
**Purpose:** Active planned work (P10) and confirmed future gaps with their
trigger conditions, rationale, and embedded design decisions. Completed
build history lives in `Product_Archive.md`.

---

## Future Phases — confirmed gaps, not yet scheduled

Surfaced by a deliberate audit against a functional/non-functional layer
checklist (Readme.md "Architecture by Layer" / SPECS.md §4). Each is listed
with a **trigger condition** (the concrete signal that means "build this
now," not a calendar date) and **rationale**, so a future session can
decide whether the trigger has actually fired instead of re-litigating
whether the gap matters.

Two design decisions are settled for items below and recorded so they are
not re-opened: MCP integration stays tenant-owned (BYO), not shipped by the
framework; the LLM self-correction loop, if built, is a separate opt-in
method, not inserted in front of the existing human DLQ escalation path.

---

### Memory Management — short-term (token-window) + long-term (vector store)

**Already implemented (not part of this gap):** the long-term, structured
half of this layer exists as the codebase Knowledge Graph (`map_codebase.py`
→ `local_knowledge_graph.py`, SPECS.md §10) — graph-based recall over files,
dependencies, guardrails, and past incidents that survives across sessions.

**Gap:** no short-term token-window truncation/summarization/sliding-window
manager, and no semantic / vector retrieval (Chroma/pgvector/etc.) anywhere
in the repo.

**Trigger:** the first tenant app that needs either (a) a conversation longer
than fits in one context window, or (b) semantic retrieval over a corpus too
large to put in a prompt directly.

**Fix sketch, when triggered:**
- Short-term: `runtime/conversation_memory.py` — message list with a
  configurable token budget (via `tiktoken`) and a pluggable eviction strategy
  (truncate-oldest first; summarization via `gw.complete()` is a reasonable v2).
- Long-term: `runtime/vector_store.py` interface (`add`, `query`) with a
  Postgres+pgvector backend as the default — consistent with this framework's
  existing Postgres-backed state (idempotency, DLQ, budget). Chroma/Pinecone
  become alternate backends behind the same interface only if a concrete tenant
  need shows up.

---

### Tool Orchestration — registration/schema-extraction, MCP

**Gap:** no `@tool`-style decorator extracting a Python function's signature
into a JSON schema; `llm_gateway.py.complete()` sends a prompt and gets text
back — no function-calling fields in the provider request.

**Design decision (settled — do not re-open without a concrete reason):** MCP
integration stays **bring-your-own** — the framework does not ship an MCP
client/server. Rationale: AgentSmith's design goal is supporting tenant apps
of "any architecture or language," and MCP is one tool-orchestration standard
among several a tenant might already use; shipping it as first-class would tie
every tenant to that standard and commit this framework to tracking MCP's spec
evolution, for a capability orthogonal to what this framework owns
(budget/redaction/tracing/HITL around an LLM call, not the orchestration
logic in front of it). If your tenant app uses MCP, treat `llm_gateway.py` as
the place the resulting LLM call flows through; the MCP client/tool-schema
layer sits in front of it in your own code.

**Trigger:** a tenant reference app whose domain needs the LLM to choose
among several tools dynamically, as opposed to fixed activity sequences.

**Fix sketch, when triggered:** a small `runtime/tool_registry.py` with a
decorator that introspects type hints/docstrings into a JSON schema,
independent of any specific orchestration protocol.

---

### Perception & Input Parsing — structured output parsing, prompt templating

**Gap:** the reference pipelines extract JSON from LLM text via bare
`re.search`+`json.loads()` with a hardcoded fallback shape — no schema
validation. No reusable prompt-template engine; prompts are inline f-strings.

**Trigger:** a second reference pipeline (or a real tenant app) that duplicates
either the JSON-extraction pattern or a near-identical prompt structure — once
there are 2+ real call sites with the same shape, not before.

**Fix sketch, when triggered:** `runtime/structured_output.py` (Pydantic model
+ `model_validate_json`, typed error on mismatch) and
`runtime/prompt_templates.py` (minimal Jinja2 or `string.Template` wrapper).

---

### Human-in-the-Loop — LLM-driven self-correction

**Gap:** every recovery path today is human-driven (DLQ edit-and-replay) or
Temporal-driven (transient-failure retry) — no path where the model sees its
own tool-call error and retries with a corrected call before any human is
involved.

**Design decision (settled):** if built, this is a **separate, opt-in method**
(e.g. `run_with_self_correction`), not inserted in front of
`run_with_recoverable_step`'s existing human-escalation path. Rationale: keeps
the already-shipped, already-tested human-escalation behavior completely
unchanged for every existing call site; a tenant who wants model-driven retry
for a specific failure class opts into the new method deliberately.

**Trigger:** a tenant reports DLQ volume dominated by an error class a model
could plausibly self-correct on the first retry — evidence from real DLQ
`reason` distribution, not a guess.

**Fix sketch, when triggered:** `run_with_self_correction(activity_name,
payload, tenant_id, max_self_correction_attempts, ...)` — on activity failure,
calls `gw.complete()` with the original payload + error message, asks the
model for a corrected payload, retries up to `max_self_correction_attempts`,
and only then falls through to enqueueing a DLQ entry exactly as
`run_with_recoverable_step` does today — reusing that path, not duplicating it.

---

### Security & Guardrails — pre-call input sanitization

**Gap:** `trace_redactor.py` redacts/anonymizes data **after** a call, for
observability. There is no symmetric **pre-call** guardrail — nothing scrubs
PII or moderates content in the prompt sent to the model.

**Trigger:** a tenant app that accepts untrusted end-user input directly into a
prompt (the current examples take structured internal data — price series,
payloads — never free-text user input).

**Fix sketch, when triggered:** a `runtime/input_guardrail.py` hook point in
`llm_gateway.py.complete()`, called before `_invoke()` — pluggable (framework
provides the call site, not a specific moderation model), matching the
framework's existing pattern of providing the mechanism and letting the tenant
supply the policy (same shape as `replay_handler`, `TENANT_WORKER_MODULE`).

---

### Reliability & Accuracy — hallucination-rate metric

**Gap:** `run-evals.py`/`eval_judge.py` score `correctness`, `tool_accuracy`,
`latency` — no metric is literally named "hallucination rate." A hallucination
shows up as a low `correctness` score, not as its own tracked number.

**Trigger:** a tenant or stakeholder needs hallucination tracked as its own
reportable number (e.g. a compliance requirement stating "< 5% hallucination
incidents" specifically, not "correctness ≥ some threshold") — the two are
not the same number.

**Fix sketch, when triggered:** add a `hallucination` field to the judge's
scored output in `.agent-rfc/fixtures/custom_judge_criteria.json` — a new
judge-prompt dimension asking specifically "did the response state something
not supported by the input/retrieved context," distinct from "was the response
correct." Additive to the existing scorecard, not a replacement for
`correctness`.

---

### Scalability & Performance — Time-to-First-Token

**Gap:** `llm_gateway.py` makes one non-streaming HTTP call per `complete()` —
there is no first-token timestamp anywhere, so TTFT cannot be measured.

**Trigger:** a tenant app with a user-facing streaming response UI (e.g. a chat
interface showing tokens as they arrive) — TTFT only matters as a UX metric
once there's a UI that benefits from streaming.

**Fix sketch, when triggered:** add a streaming code path to
`runtime/provider_dispatch.py` (provider SDKs already support streaming —
this is wiring, not new capability), record the first-chunk timestamp in
`_invoke()`, add `ttft_ms` alongside existing `cost_usd`/token counts in
`_record_span_attributes`. Non-streaming `complete()` stays the default —
streaming is an opt-in mode.

---

### Data Bias & Fairness — fairness/robustness evaluation

**Gap:** no fairness, bias, or robustness metric (demographic parity, disparate
impact, adversarial-input robustness) is tracked anywhere in the eval
framework.

**Trigger:** a tenant app whose domain has a real fairness exposure (e.g.
anything making decisions about people — lending, hiring, eligibility).
Genuinely not applicable to the current reference examples (oil price
forecasting has no fairness dimension).

**Fix sketch, when triggered:** a separate evaluation dataset — fairness test
sets (paired inputs differing only in a protected attribute, checking for
outcome parity) don't usually overlap with task-correctness golden sets. Scope
as its own `.agent-rfc/fixtures/fairness_evals.json` with its own judge
criteria, evaluated by `scripts/run-evals.py --suite fairness` (new flag).

---

*Build history (P0–P10) lives in `Product_Archive.md`.
SPECS.md and Readme.md are the canonical specification record.
OPERATIONS.md is the canonical operator-facing reference.*
