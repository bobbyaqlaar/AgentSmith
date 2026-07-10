<p align="center">
  <img src="assets/Logo_AgentSmith.png" alt="Project Logo" width="200">
</p>

# AgentSmith

**One install. Every agent. Every project.**

AgentSmith is a single-command setup that provisions the complete AI agent lifecycle environment on your machine or team server. Install it once and every repository you work in gets guardrails, observability, evaluation, self-improvement, and CI/CD — automatically.

---

## What It Sets Up

| Layer | What you get |
|---|---|
| **IDE Guardrails** | `.cursorrules`, `CLAUDE.md`, `.agents/skills/` — written for Cursor, Claude Code, and Antigravity on every `git checkout` |
| **Git Hooks** | Pre-commit safety checks, commit message linting, automatic semantic versioning, AST codebase mapping — globally, across every repo |
| **Observability** | Arize Phoenix tracing dashboard — one instance per machine or team, serving all projects with per-project namespacing |
| **Evaluations** | Golden dataset + LLM-as-judge scorecard that gates every PR, calibrated continuously from production traces |
| **Multi-Agent Orchestration** | Architect → Developer → Validator pipeline, running locally on Ollama or on cloud frontier models |
| **Knowledge Graph** | AST-driven codebase graph, auto-updated on every commit and checkout — zero context drift |
| **Self-Improvement** | Human-in-the-Loop promotion loop: production failures become test cases become guardrail rules |
| **Cost & Budget Guard** | Dual-tier circuit breaker — burst velocity limit + monthly spend cap with cross-platform notifications |
| **CI/CD** | GitHub Actions workflows for TypeScript/React, Python/FastAPI, and Go — written automatically per project |
| **Agent Identity** | Every span, log entry, and trace is tied to an orchestrator, sub-agents, and a real human owner |

---

## Prerequisites

### System tools

| Tool | Purpose | Check |
|---|---|---|
| Python 3.11+ | All scripts, runtime, evals | `python3 --version` |
| Git 2.x | Hooks, versioning, CI | `git --version` |
| Docker 20+ | Phoenix, Ops Portal, Postgres | `docker --version` |
| Node.js 20+ | Ops Portal, In-App Widget | `node --version` |
| `gh` CLI | Promotion PRs, CI secrets | `gh --version` |
| Ollama | Local/offline dev mode only | `ollama --version` |

### API keys — add to `~/.zshrc`

```bash
# ── Directories ──────────────────────────────────────────────────────────────
export REPO_DIR="$HOME/repos"            # root for all your repos; adjust if different
export AGENTSMITH_DIR="$REPO_DIR/AgenticFramework"

# ── Identity (required for every span and log entry) ─────────────────────────
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# ── LLM providers (hybrid mode — add whichever you use) ──────────────────────
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GROQ_API_KEY="gsk_..."          # optional: fast/cheap inference

# ── Observability ─────────────────────────────────────────────────────────────
export AGENT_PHOENIX_ENDPOINT="http://localhost:6006"   # default; change for team server

# ── Budget / routing ──────────────────────────────────────────────────────────
export AGENT_MONTHLY_USD_CAP="50"      # hard spend cap per month across all projects
                                        # (also the production LLMGateway's default cap
                                        # if a tenant doesn't pass budget_cap_usd explicitly —
                                        # falls back to 150.0 if this var is unset)
export AGENT_JUDGE_MODEL="claude-sonnet-4-6"            # model used to grade evals
```

### `.env` files — there are two, in different places

**AgentSmith root `.env`** — controls the Ops Portal and shared Docker Compose stack.
Run from the AgentSmith framework directory (`AgenticFramework/`):

```bash
# Run from: AgenticFramework/
cp portal/.env.example .env
# Then edit .env with the values below
```

```bash
# AgenticFramework/.env
DATABASE_URL=postgresql://phoenix:phoenix@localhost:5433/agenticframework

# Portal basic auth — portal refuses to serve without these. Generate a strong
# random password: openssl rand -base64 24
OPS_PORTAL_USER=ops
OPS_PORTAL_PASSWORD=<strong-password>           # generate: openssl rand -base64 24

# Bearer token gating /api/sync/history and /api/runs/ingest on the portal.
# Copy this same value into ~/.zshrc (OPS_PORTAL_SYNC_TOKEN) and each tenant
# app's GitHub Actions secrets so local scripts and CD pipelines can call the portal.
# Generate: openssl rand -hex 32
OPS_PORTAL_SYNC_TOKEN=<random-secret>           # generate: openssl rand -hex 32

# Bearer token gating /api/audit/append — used by install-ai-stack.sh to post
# hook-bypass events. Portal-side only; not needed in ~/.zshrc.
# Generate: openssl rand -hex 32
AUDIT_LOG_WRITE_TOKEN=<random-secret>           # generate: openssl rand -hex 32

# HMAC-SHA256 key used to sign every audit event at write time (tamper detection).
# At read time the portal re-signs and compares — a mismatch means the row was altered.
# SERVER-SIDE ONLY — never export to ~/.zshrc or tenant apps.
# ROTATION WARNING: old events stay signed with the old key and fail re-verification
# after a rotation. Generate once and keep stable: openssl rand -hex 32
AUDIT_LOG_HMAC_KEY=<random-secret>              # generate: openssl rand -hex 32  — rotate with care

HITL_ENCRYPTION_KEY=<32-byte-hex>               # generate: openssl rand -hex 32
```

**Tenant app `.env`** — runtime config for each individual agentic app you build.
Lives in your own app repo root (e.g. `my-oil-price-app/.env`), **not** in the AgentSmith folder:

```bash
# my-tenant-app/.env
TENANT_ID=my-tenant
ANTHROPIC_API_KEY=sk-ant-...
AGENT_PHOENIX_ENDPOINT=http://localhost:6006
OPS_PORTAL_URL=http://localhost:3000
OPS_PORTAL_SYNC_TOKEN=<same value as AgenticFramework/.env>
DATABASE_URL=postgresql://user:pass@localhost:5433/my-tenant-db
ENVIRONMENT=production
HITL_ENCRYPTION_KEY=<same value as AgenticFramework/.env>
```

### GitHub Actions secrets

Set these in **Settings → Secrets and variables → Actions** for each tenant repo:

| Secret | Required for |
|---|---|
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | CI eval judge + hybrid-mode tests |
| `AGENT_PHOENIX_ENDPOINT` | Trace export from CI (optional — CI still passes without it) |
| `OPS_PORTAL_URL` | CD → portal history sync |
| `OPS_PORTAL_SYNC_TOKEN` | CD → portal history sync |
| `DEPLOY_COMMAND` | Actual deploy step (platform-specific — Fly, Railway, ECS, GCP Cloud Run, etc.) |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | GCP Cloud Run deploys — keyless WIF auth (preferred over SA key) |
| `GCP_SERVICE_ACCOUNT` | GCP Cloud Run deploys — SA email used with WIF |
| `GCP_PROJECT_ID` | GCP Cloud Run deploys — referenced in `DEPLOY_COMMAND` as `$GCP_PROJECT_ID` |

Set on **GitHub Environments** (`staging` / `production`), not at the repo level, so each environment
can target a different GCP project or service. See OPERATIONS.md §D.5b for the one-time WIF setup.

---

## Quick Start

```bash
# 1. Install
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash

# 2. Activate
source ~/.zshrc

# 3. Set your identity
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# 4. Choose your mode
ai-mode-local    # 100% offline — Ollama on your GPU (free)
# or
ai-mode-hybrid   # Cloud frontier APIs — Claude + GPT-4o

# 5. Start the observability dashboard
ai-dashboard-start
# → http://localhost:6006

# 6. Apply to a project
cd /path/to/your/project
git init -b main
# → hooks fire, .cursorrules written, CI workflows created, Knowledge Graph seeded
```

---

## The Ten Pillars

AgentSmith is built around ten operational guardrails that together cover the full agent lifecycle.

**1. Requirements & Design** — Agents are blocked from writing code unless a spec exists in `.agent-rfc/`. Every change is mapped to a written requirement before execution begins.

**2. Build Architecture (Ponytail)** — Native platform libraries over custom abstractions. Minimal dependency trees. A five-step analysis before any new file is created.

**3. Tracing & Evaluations** — Every token, tool call, and latency metric is streamed to the Arize Phoenix dashboard via OpenTelemetry. Nothing is lost between sessions.

**4. Testing Guardrails** — Every change requires paired tests. CI enforces this on every pull request. Existing regression tests are never cleared to force a green build.

**5. Operations & Self-Improvement** — `.agent-history.log` captures structured events (INFO / MINOR / MAJOR / CRITICAL). MAJOR and CRITICAL entries are protected until a human resolves them via HITL.

**6. Interface Constraints (Caveman)** — Agents output code and data only. No pleasantries, summaries, or meta-commentary.

**7. Stack-Specific Rules** — TypeScript/React, Python/FastAPI, and Go rules injected into all three IDEs automatically on checkout.

**8. Observability Wire** — The OTel endpoint is embedded in `.cursorrules` so IDE-level agent requests stream to the dashboard without additional configuration.

**9. Multi-Agent Orchestration** — Stateful Architect → Developer → Validator pipeline with HITL pause support. Runs fully offline (Ollama) or on cloud frontier APIs with automatic network fallback.

**10. Cost-Optimisation Routing** — Token complexity and semantic analysis route each task to the cheapest capable model. A dual-tier circuit breaker prevents budget bleed.

---

## Architecture by Layer

The Ten Pillars above are this framework's own operational guardrails — the
things AgentSmith enforces on every project it touches. This section
is a different cut through the same system: the **functional and
non-functional layers** any agentic application needs, mapped to exactly
what AgentSmith provides for each one today, what it deliberately
leaves to the tenant app, and what's genuinely not built yet. Read this
before adding a new capability — several of the "not built" items below
were evaluated and deliberately deferred or replaced with a different
mechanism; the reasoning is recorded so that ground doesn't get re-covered.

### Functional layers

**1. Reasoning & Planning** — decomposing a high-level goal into a
multi-step plan.
Provided as a *pattern*, not a library: `scripts/multi_agent_system.py`'s
LangGraph `StateGraph` (Architect → Developer → Validator, with a
conditional HITL edge) and `scripts/local_agent_stack.py`'s pure-Python
equivalent (`MAX_REVISIONS`-capped revision loop) are fixed three-node
topologies, not a generic planner. A tenant app with a different shape
(more nodes, dynamic branching, a true ReAct interleaved-tool-call loop)
writes its own graph — these two files are the reference shape to copy,
the same way `runtime/workflows/base_workflow.py` is a reference Temporal
workflow, not a deployable one.

**2. Tool Orchestration** — calling external functions/APIs/retrieval
systems.
`runtime/workflows/base_workflow.py`'s `run_with_recoverable_step` is the
*execution* half (run an activity, recover from its failure) but there is
**no tool-registration layer** — no `@tool` decorator that turns a Python
function's signature into a JSON schema the LLM can call, and
`runtime/llm_gateway.py`'s `complete()` does not put tool/function-calling
fields in the provider request at all (confirmed by reading the gateway:
it sends a prompt and gets text back, nothing else). A tenant app wanting
LLM-driven tool selection (the model deciding *which* tool to call) needs
its own schema layer on top — Model Context Protocol (MCP) servers are a
reasonable fit if you want one, and nothing here conflicts with using
one, but the framework doesn't ship an MCP client/server itself.
**Model Context Protocol specifically:** not integrated. If your tenant
app needs MCP, treat `llm_gateway.py` as the place a tool-call's *resulting
LLM call* still flows through (for budget/redaction/tracing), with the
MCP client/tool-schema layer sitting in front of it in your own code.

**3. Memory Management** — short-term (conversation/context) vs. long-term
(knowledge base/vector store).
**Partially implemented.** The long-term half exists as a **graph-structured
codebase knowledge base**: `scripts/map_codebase.py` AST-walks the repo into
`scripts/local_knowledge_graph.py`'s NetworkX `DiGraph`, persisted as JSON
node-link at `.agent-rfc/fixtures/knowledge_graph.json` and auto-rebuilt by
the `post-commit`/`post-checkout` hooks (and now validated in CI via
`verify_system.py --check-kg`). It is queried, not dumped — `kg.fetch_subgraph_context_window(target, hops=2)`
returns a ~200-token subgraph of the files, imports, guardrails, and past
production incidents around an anchor file (SPECS.md §10). This is the
framework's long-term, *structured* (not vector) memory.

**Why this matters for a brand-new session — refactoring, changing, and
fixing defects.** An agent (or human) starting cold, with zero prior
conversation context, can reconstruct what it needs to safely touch the
code *from the graph alone*:
- **Before adding code** — query the graph to answer Pillar 2's first
  question, *"does this already exist?"*, instead of re-deriving the
  codebase from scratch and duplicating something. New files must be
  registered in the graph before creation (SPECS.md §4 Pillar 2).
- **Before changing/refactoring** — `impacted_files(path)` and the
  `IMPORTS` edges give the blast radius: every file that depends on the
  one you're about to change, so a rename or signature change isn't a
  guess. This is the "what does this affect / are there downstream graph
  dependencies?" steps of the 5-step analysis.
- **When fixing a defect** — `CAUSED_INCIDENT` edges link source files to
  `ProductionIncident` nodes distilled from `.agent-history.log`, so a new
  session can see *which prior bugs touched this file and how they were
  resolved* — long-term recall that would otherwise have died with the
  session that fixed them.
- **Token economy** — pulling a bounded subgraph instead of reading whole
  files is what keeps a fresh session's context lean enough to actually
  reason (the §3 "Headroom" guardrail).

**Still genuinely absent** (the other two thirds of this layer): there is
no short-term **conversation/token-window** manager
(truncation/summarization/sliding-window) anywhere in this repo, and no
**semantic / vector** retrieval (Chroma/pgvector/Pinecone or otherwise) —
the graph is structured lookup, not embedding similarity. Two things that
are present but are *not* this layer and shouldn't be confused with it:
Temporal's durable-execution event history (workflow *progress* survives a
crash — `runtime/workflows/base_workflow.py`) and LangGraph's `PostgresSaver`
checkpointer in `scripts/multi_agent_system.py` (dev/hybrid mode only —
`MemorySaver` is prohibited in production, SPECS.md §25). If your tenant app
needs conversation memory or vector retrieval, build it as its own
component — see FIXES_AND_CLEANUP.md "Memory Management" for the intended
shape — rather than assuming one is implied here.

**4. Perception & Input Parsing** — understanding ambiguous user intent
and routing tasks.
Two narrow, real implementations exist, not a general intent classifier:
`scripts/multi_agent_system.py`/`local_agent_stack.py` extract structured
JSON from raw LLM text via `re.search(r'\{.*\}', ...)` + `json.loads()`
with a hardcoded fail-shape fallback — no Pydantic/JSON-schema validation,
no "instructor"-style auto-coercion. There's also no dynamic prompt-template
engine (no Jinja2 or `PromptTemplate` abstraction) — prompts are built as
inline f-strings, once, per call site. Both are real gaps if you need
strict structured-output guarantees or prompt reuse across many call
sites; the fix is the same shape either way — add a small,
focused module (e.g. `runtime/prompt_templates.py`,
`runtime/structured_output.py`) rather than growing inline string-building
across every caller once it's needed in more than one place.

**5. Human-in-the-Loop (HITL)** — pausing for approval/escalation on
high-risk or low-confidence actions.
The most built-out layer in the framework, with two distinct mechanisms
for two distinct situations — **don't conflate them**:
- **Approve/reject gate** (`BaseAgentWorkflow.run_with_hitl_gate`) — an
  explicit `needs_hitl` flag from an activity pauses the workflow on a
  boolean signal up to a 24h timeout; reject or timeout dead-letters the
  workflow *terminally* (it does not stay alive).
- **Edit-and-resume gate** (`BaseAgentWorkflow.run_with_recoverable_step`)
  — for failures a human *fixes* rather than approves/rejects (the
  canonical example: a tool call hallucinates `{"account_status":
  "active"}` where the schema wants `"status"`). The workflow stays
  **alive**, parked on a per-`gate_id` signal; a human edits the failing
  payload in the Ops Portal's `/dlq/<tenantId>` view and the same
  execution resumes with the correction — not a fresh run.

**Why Temporal signals, not a third-party HITL platform:** an external
review proposed three off-the-shelf approaches for this — (a) Slack +
Retool + a job queue (BullMQ/Celery) wired by webhook, (b) LangGraph's
native `interrupt`/checkpoint-resume primitive, (c) a durable-execution
engine's own `await step.waitForEvent(...)`-style pause. (c) is what's
built here, deliberately, because the framework already runs Temporal for
workflow orchestration — adding Slack+Retool+a second queue (a) would mean
running a second orchestration stack for no benefit, and LangGraph's
interrupt primitive (b) would mean replacing the workflow engine outright.
If you're evaluating HITL approaches for a *new* stack that isn't already
on Temporal, (a) or (b) may be the right call there — the point isn't
"Temporal is always correct," it's "don't re-evaluate this for *this*
framework," since the choice was made against the engine already in use.

**The portal-to-worker bridge is a per-tenant webhook, not a direct
Temporal client in the portal — also a deliberate choice, not an
oversight.** The Ops Portal (Next.js) could embed Temporal's Node SDK and
signal workflows directly; instead, `portal/lib/dlq.ts`'s `replayDlqEntry()`
HMAC-signs the edited payload and POSTs it to **that tenant's own**
`replay_webhook_url` (synced from `tenant.yaml`'s `hitl.*` section),
received by `runtime/replay_webhook_server.py` (a reference, not a
hardened receiver — tenants adapt it into their own web framework), which
holds the actual Temporal client. Two reasons this was chosen over a
direct portal-side client: (1) `runtime/dead_letter.py`'s `replay_handler`
is deliberately engine-agnostic — a Celery-based tenant implements the
same extension point without Temporal at all, and a portal-side Temporal
client would silently assume every tenant uses Temporal; (2) per-tenant
routing means a human-in-the-loop fix always reaches the specific team
running that tenant's worker, never a single shared endpoint serving
every tenant's traffic.

### Non-functional layers

**6. Observability & Traceability** — chain-of-thought logging, latency,
token usage, cost.
Fully wired, not partial: every span carries `tenant.id`, `agent.owner_id`,
`agent.name`, `agent.role`, `llm.model_name`, `llm.gateway.cost_usd`
(`runtime/llm_gateway.py`'s `_record_span_attributes`), streamed via
OpenTelemetry/OpenInference to Arize Phoenix. Cost and token counts are
tracked per call; **Time-to-First-Token is not** — `llm_gateway.py` makes
a single non-streaming HTTP call per `complete()`, so there is no
first-token timestamp to record. If a tenant app needs TTFT specifically
(e.g. a chat UI with a "thinking" indicator), that requires adding
streaming support to the provider dispatch layer first — TTFT can't be
measured without it.

**7. Reliability & Accuracy** — capping hallucinations, task-precision
targets, auto-retrying failed tool calls.
`scripts/run-evals.py`/`scripts/eval_judge.py` score `correctness`,
`tool_accuracy`, and `latency` per golden-dataset case via an LLM judge —
**there is no metric literally named "hallucination rate"**; a
hallucination shows up as a low `correctness` score, not as its own
tracked number. If you need a hallucination rate specifically (as opposed
to a correctness proxy for it), that's a new judge-criteria dimension to
add in `.agent-rfc/fixtures/custom_judge_criteria.json`, not something to
infer from existing scores. "Auto-retry failed tool calls" is real but
two-tiered, and the tiers matter: Temporal's own activity retry policy
handles **transient** failures (network blips, rate limits) automatically;
`run_with_recoverable_step`'s `RetryPolicy(maximum_attempts=1)` override
deliberately **disables** that automatic retry for the *gated* activity
specifically, because a validation/hallucination-shaped failure won't
succeed on a bare retry — it needs a *different* payload, which only a
human (today) can supply. **There is no LLM-driven self-correction loop**
(the model retrying its own tool call after seeing the error) anywhere in
the repo — every recovery path that exists is human-driven (DLQ
edit-and-replay) or Temporal-driven (transient-failure retry), never
model-driven. That's a real, named gap if you wanted the agent itself to
attempt a fix before escalating to a human.

**8. Security & Guardrails** — prompt-injection protection, input
sanitization, data anonymization.
**Asymmetric, and worth knowing which side you're on:** `runtime/trace_redactor.py`
redacts/anonymizes data **after** a call, for observability (what gets
written to Phoenix/logs) — staging hashes, production truncates +
encrypts into a HITL blob. There is **no symmetric guardrail before a
call** — no PII scrubber or content moderator (e.g. a Llama Guard-style
filter) sits between user input and the prompt actually sent to the
model. A tenant app handling untrusted user input that could contain
injected instructions or PII that must never reach the model at all needs
its own pre-call guardrail; redaction here only protects what's
*recorded*, not what's *sent*.

**9. Explainability** — meeting stakeholder transparency/auditing
expectations.
Built at the infrastructure level, not as a "show your reasoning" feature:
the Ops Portal's audit log (`audit_log` table) HMAC-signs every admin/system
event with a DB-trigger-enforced append-only constraint — `GET /api/audit`
recomputes the signature on read and flags `verified: false` on tampering,
including a privileged-attacker scenario (disable trigger, mutate row,
re-enable trigger) that the signature layer still catches. Combined with
full-trace OTel spans in Phoenix, every action is auditable after the
fact. What's not here: no per-decision natural-language explanation
generation ("the agent chose X because Y") — explainability here means
"every action is traceable and tamper-evident," not "every action narrates
its own reasoning."

**10. Scalability & Performance** — concurrent instances, horizontal
scaling, latency (e.g. TTFT under 1s).
Two separate mechanisms cover two separate scaling axes: Temporal's worker
pool model (`tenant.isolation: shared` — many tenants on one fleet,
partitioned by `tenant.id` in task routing; `dedicated` — a tenant gets
its own Kubernetes worker pool, `runtime/k8s/dedicated-tenant/`) covers
*workflow* concurrency/isolation. `templates/onprem-deploy/`'s canary
routing (Traefik's native `weighted`/`mirroring` service kinds, or Envoy's
`weighted_clusters`/`request_mirror_policies`, customer's choice) covers
*app-version* traffic-shaping for on-prem deployments — chosen over a
single fixed proxy because on-prem customers' ops teams already have a
preference one way or the other, and forcing one would mean a second
unfamiliar tool to operate. Real limitation worth flagging again from
layer 6: **TTFT specifically can't be measured** without adding streaming
to the LLM Gateway first — there's no latency-budget enforcement keyed to
"first token," only total-call latency.

**11. Data Bias & Fairness** — continuous evaluation against fairness/
robustness metrics.
**Not implemented.** No fairness or bias metric is tracked anywhere in
`run-evals.py`/`eval_judge.py`/`shadow-eval.py` — the judge scores
correctness/tool-accuracy/latency, not demographic parity, robustness
under adversarial input, or any standard fairness metric (equalized odds,
disparate impact, etc.). If this matters for your tenant app, it's a new
judge-criteria dimension and likely a separate evaluation dataset
(fairness test sets don't usually overlap with task-correctness golden
sets) — there's no existing scaffold to extend, this is greenfield.

**12. Continuous Improvement** — learning from production to update the
golden dataset/evals, avoiding drift.
Two independent loops, serving different purposes — know which one you're
looking at:
- **HITL promotion loop** (`scripts/sync-ui-feedback.py`, `ai-test-evals`,
  `ai-stack-promote`) — a human annotates a Phoenix span as
  approved/rejected; an approved fix gets distilled into a new
  `golden_evals.json` case and judge-criteria rule, gating every future PR.
  This is the mechanism behind UserManual.md §9 and the "compounding
  quality flywheel" framing elsewhere in this doc.
- **Shadow-eval sampler** (`scripts/shadow-eval.py`, opt-in via
  `workflow-templates/shadow-eval.yml`) — samples 5% of `environment=production`
  Phoenix spans on a schedule, judges them the same way `run-evals.py`
  does (shared logic in `scripts/eval_judge.py`), writes results back as
  Phoenix annotations tagged `eval.type: shadow`. This is *passive*
  drift detection — it surfaces failing patterns as "suggested
  promotions" in the Ops Portal (`portal/lib/promotions.ts`) for a human
  to act on; it never auto-promotes anything itself, by design — same
  HITL gate as the first loop, just a different discovery mechanism for
  what needs reviewing.

---

## Supported Stacks

| Stack | Detected by | CI workflow |
|---|---|---|
| TypeScript / React | `package.json` | `ci-ts-react.yml` |
| Python / FastAPI | `requirements.txt` / `pyproject.toml` | `ci-python-fastapi.yml` |
| Go | `go.mod` | `ci-go.yml` |
| Generic | *(fallback)* | *(hooks only, no CI workflow)* |

Every `ci-<stack>.yml` also runs the Ten-Pillars CI gates (FIXES_AND_CLEANUP.md P10): Knowledge Graph validation (Pillar 2), an RFC gate (Pillar 1, enforced only when `.agenticframework/org-policy.yaml` is present), IDE config drift detection (Pillar 6/7), and a non-blocking framework health check (Pillar 3/5). The `ci-ts-react.yml` and `ci-go.yml` workflows set up Python alongside their native toolchain to run these gates.

---

## Execution Modes

### Local Offline
Everything runs on your machine. No API keys. No cost.

```
Ollama (llama3 / mistral / gemma2)  ←→  Local Phoenix (:6006)
```

### Hybrid Cloud
Frontier models for complex tasks, open-source for everything else. Automatic fallback to local if the network drops.

```
Claude 3.5 Sonnet / GPT-4o  ←→  Open-source via Groq/Together  ←→  Local Phoenix
```

Switch modes instantly — no restart, no config file edits:

```bash
ai-mode-local     # switch to offline
ai-mode-hybrid    # switch to cloud
ai-stack-status   # show current state + network connectivity
```

---

## Multi-Repository & Monorepo

The framework installs once at the machine level. Every repository on the machine inherits the git hooks automatically. No per-project setup steps.

```bash
# Apply to any existing repo instantly
cd /path/to/existing-repo && git init
```

Monorepos are fully supported. Each sub-package can have its own `.agent-rfc/` for service-level specs, with a root `.agent-rfc/` for cross-cutting architecture decisions.

---

## Observability

All projects on the machine share a single Arize Phoenix instance. Traces are namespaced by `project.name` — filter in the UI to see any individual project.

For teams, run Phoenix as a shared service with the included Docker Compose file (PostgreSQL-backed):

```bash
docker compose up -d
# All team members set: export AGENT_PHOENIX_ENDPOINT="http://<server-ip>:6006"
```

---

## Evaluation & Self-Improvement

The golden dataset starts with framework-provided baseline cases and grows automatically from production traces via the HITL loop. Every approved production trace becomes a new test case that gates future PRs — creating a compounding quality flywheel.

```
Dev evals (PR gate)  ←←←  Golden dataset  →→→  Production calibration (HITL loop)
```

Run evals locally:
```bash
ai-test-evals
```

Promote a production fix to the golden dataset:
```bash
ai-stack-promote <case-id> "<input query>" "<correct output>"
```

---

## Agent Identity

Every agent run is fully traceable to a human owner across all projects and sessions:

```bash
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"
```

Every OTel span, log entry, and HITL record carries `agent.owner_id`, `agent.name`, `agent.role`, `agent.session_id`, and parent-child span linkage between orchestrators and sub-agents. Filter Phoenix by `agent.owner_id` to see all activity across all your projects.

---

## CI/CD

GitHub Actions workflows are written automatically by the `post-checkout` hook and enforce the same guardrails as your local environment:

- Type checking, linting, and tests on every pull request
- Eval scorecard with configurable quality threshold
- Graceful skip on greenfield projects until a golden dataset exists
- Post-deploy promotion of approved production traces back into the golden dataset

Required GitHub secrets: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. `AGENT_PHOENIX_ENDPOINT` is optional.

---

## Example: Building an Oil Price Tracker & Chemical Order Agent

This walkthrough shows the complete happy path — from an empty folder to a production-ready multi-agent system — using AgentSmith. The app tracks and predicts oil prices and automatically places orders for chemicals whose prices are directly linked to oil, triggered when the predicted price crosses a configured threshold.

### What the System Does

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Ingestion Agent │───►│ Prediction Agent  │───►│  Decision Agent     │
│                 │    │                  │    │                     │
│ Fetches oil     │    │ Time-series model │    │ Compares predicted  │
│ price data from │    │ forecasts next    │    │ price vs. threshold │
│ market APIs     │    │ 7-day price range │    │ per chemical        │
└─────────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                           │
                                                           ▼
                                               ┌─────────────────────┐
                                               │   Order Agent       │
                                               │                     │
                                               │ Places purchase     │
                                               │ orders via supplier │
                                               │ API when threshold  │
                                               │ is breached         │
                                               └─────────────────────┘
```

### Step 0 — Install the Framework *(once per machine)*

Before any project work, run the installer once on your machine. This is a machine-level operation — you never run it again for subsequent projects.

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash

# Activate shell functions
source ~/.zshrc

# Set your identity (all traces and logs will be attributed to you)
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# Install local GPU models (required for local mode; skip if using hybrid only)
ollama pull llama3 && ollama pull mistral && ollama pull gemma2

# Choose your mode and start the dashboard
ai-mode-hybrid        # or ai-mode-local for fully offline
ai-dashboard-start    # http://localhost:6006
```

From this point on, every `git init` or `git clone` on this machine automatically receives the full framework — hooks, IDE rules, CI workflows, and Knowledge Graph — with no further installation steps.

> **Already installed?** Skip to Step 1. The installer is idempotent — safe to re-run after framework upgrades.

---

### Step 1 — Create the Repository

```bash
mkdir oil-price-agent && cd oil-price-agent
git init -b main
git remote add origin https://github.com/org/oil-price-agent.git
```

The `post-checkout` hook fires immediately:

```
🔧 AI Stack Hook: Analysing repository type... [Detected: PYTHON_FASTAPI]
✅ AI Stack Hook: Created .agent-rfc/ directory
✅ AI Stack Hook: Created stack-specific .cursorrules file
✅ AI Stack Hook: Created CLAUDE.md (Claude Code instructions)
✅ AI Stack Hook: Created Antigravity skill structure
✅ AI Stack Hook: Written ci-python-fastapi.yml into GitHub Workflows
🏗️  Constructing baseline Knowledge Graph architecture...
✅ Knowledge Graph seeded with 3 guardrail nodes
```

You now have a fully configured project with IDE rules for all three agents, a CI pipeline, and a baseline golden dataset — before writing a single line of code.

### Step 2 — Write the RFC Specification

Before any agent touches code, the spec must exist.

```bash
touch .agent-rfc/001-oil-price-tracker.md
```

```markdown
# RFC 001 — Oil Price Tracker & Chemical Order Agent

## Objective
Build a multi-agent system that monitors crude oil prices, forecasts 7-day
price movements using a time-series model, and places purchase orders for
chemicals (benzene, ethylene, propylene) when the predicted price drops
below a configured threshold.

## Agent Roles
- **Ingestion Agent**: Polls EIA / commodity API every 6 hours; stores to TimescaleDB
- **Prediction Agent**: Runs Prophet forecast on latest 90-day window; writes forecast to DB
- **Decision Agent**: Reads forecast; compares to per-chemical thresholds in config
- **Order Agent**: Calls supplier REST API to place purchase order; logs outcome

## Files to Create
- `agents/ingestion_agent.py`
- `agents/prediction_agent.py`
- `agents/decision_agent.py`
- `agents/order_agent.py`
- `orchestrator.py`
- `config/thresholds.yaml`
- `tests/test_decision_agent.py`

## Thresholds (initial)
| Chemical    | Order if predicted price ($/bbl oil eq.) | Order qty |
|-------------|------------------------------------------|-----------|
| Benzene     | < 72.00                                  | 500 MT    |
| Ethylene    | < 68.00                                  | 1,200 MT  |
| Propylene   | < 65.00                                  | 800 MT    |

## Acceptance Criteria
- [ ] Forecast MAPE < 8% on 30-day back-test
- [ ] Order placed within 60s of threshold breach detection
- [ ] All API calls retried with exponential backoff (no swallowed errors)
- [ ] Full trace in Phoenix for every forecast + order cycle
```

### Step 3 — Start the Stack

```bash
ai-mode-hybrid        # Claude 3.5 Sonnet for architecture, Llama3 for implementation
ai-dashboard-start    # http://localhost:6006
ai-stack-check        # confirm everything is healthy
```

### Step 4 — The Architect Agent Designs the System

In your IDE (Cursor, Claude Code, or Antigravity), the agent reads the RFC automatically before planning. It queries the Knowledge Graph for existing dependencies, then proposes the minimal architecture:

```
🧠 [Architect Agent] Reading .agent-rfc/001-oil-price-tracker.md...
🧠 [Architect Agent] Querying Knowledge Graph for existing modules...
🧠 [Architect Agent] Applying PONYTAIL: using Prophet (standard), httpx (standard), psycopg2 (standard)
🧠 [Architect Agent] No custom abstractions required — native async + standard retry library sufficient

Blueprint:
  orchestrator.py          ← LangGraph StateGraph, 4 nodes
  agents/ingestion_agent.py ← httpx + psycopg2, no ORM
  agents/prediction_agent.py ← Prophet, outputs JSON forecast to DB
  agents/decision_agent.py  ← pure logic, reads config/thresholds.yaml
  agents/order_agent.py     ← httpx with tenacity retry, logs to .agent-history.log
```

The Architect span appears instantly in Phoenix under `project.name = "oil-price-agent"`.

### Step 5 — The Developer Agent Implements

The Developer agent writes code under Caveman constraints — code blocks only, no commentary. Each file written triggers a Knowledge Graph update linking the new node to its imports.

```python
# agents/decision_agent.py  (excerpt — written by Developer Agent)
import yaml
from dataclasses import dataclass
from typing import Optional

@dataclass
class OrderSignal:
    chemical: str
    predicted_price: float
    threshold: float
    order_qty_mt: int

def evaluate_thresholds(forecast: dict, config_path: str = "config/thresholds.yaml") -> list[OrderSignal]:
    with open(config_path) as f:
        thresholds = yaml.safe_load(f)

    signals = []
    for chemical, cfg in thresholds["chemicals"].items():
        predicted = forecast.get(chemical)
        if predicted is None:
            continue
        if predicted < cfg["threshold_usd_bbl"]:
            signals.append(OrderSignal(
                chemical=chemical,
                predicted_price=predicted,
                threshold=cfg["threshold_usd_bbl"],
                order_qty_mt=cfg["order_qty_mt"]
            ))
    return signals
```

### Step 6 — The Validator Agent Catches Issues

The Validator scans the generated code against March of Nines rules. On the first pass it catches a problem in the order agent:

```
🚨 [Validator Agent] Checking agents/order_agent.py...
❌ Validator Error: except block at line 47 is empty — swallowed exception detected
   → Routing back to Developer Agent for correction
```

The Developer agent fixes it, adding proper error logging and retry logic. The corrected version passes:

```
✅ [Validator Agent] All March of Nines checks passed
✅ [Validator Agent] Retry logic present (tenacity.retry)
✅ [Validator Agent] No empty catch blocks
✅ Multi-agent workflow APPROVED
```

### Step 7 — Commit and Watch the Hooks Run

```bash
git add .
git commit -m "feat(agents): implement oil price ingestion, prediction, and order pipeline"
```

```
📝 AI Guardrails: Validating commit message format...
✅ Commit message lint passed

🚨 AI Guardrails: Reviewing staged code before commit...
✅ Guardrail Audit Passed. Codebase is clean.

🔍 [Codebase Mapper] Executing AST structural sweep...
✅ Knowledge Graph updated: 6 new CodebaseFile nodes, 14 DEPENDS_ON edges

✅ Local Semantic Tag v0.1.0 generated successfully
[2026-06-22 11:34:01] Successful Commit: v0.1.0 - feat(agents): implement oil price...
```

### Step 8 — Open a Pull Request

GitHub Actions picks up the commit automatically:

```
CI: Python/FastAPI Guardrails

✅ ruff check .
✅ pytest (12 tests passed)
⚠️  Eval scorecard: golden dataset has 2 cases — below minimum threshold (3).
    Quality gate will activate on next PR once dataset is populated.
    Tip: run 'ai-test-evals' locally to add cases.
```

The PR is ready to merge. The eval quality gate is already watching — it will enforce correctness thresholds from the next PR onward.

### Step 9 — Production: The Agent Places Its First Order

The system runs in production. A forecast cycle completes:

```
Predicted WTI crude: $67.40/bbl  (7-day horizon)
→ Benzene threshold: $72.00  — BREACH DETECTED (predicted $67.40 < $72.00)
→ Ethylene threshold: $68.00 — BREACH DETECTED (predicted $67.40 < $68.00)
→ Propylene threshold: $65.00 — no breach

Placing order: Benzene 500 MT  ... ✅ Order #BNZ-20260622-001 confirmed
Placing order: Ethylene 1200 MT ... ✅ Order #ETH-20260622-001 confirmed
```

Every step streams to Phoenix. Open `http://localhost:6006`, filter by `project.name = "oil-price-agent"` and expand the trace to see:

- `ingestion_node` → fetch duration, rows written to DB
- `prediction_node` → Prophet runtime, MAPE score, forecast values
- `decision_node` → threshold evaluation, chemicals triggered
- `order_node` → API latency, order IDs, retry count

### Step 10 — Self-Improvement: A Bad Prediction Gets Promoted

One week later, the Prediction Agent underestimates a price spike. The order is placed unnecessarily (false positive). You review the Phoenix trace, annotate it:

```
Phoenix UI → Traces → prediction_node span → Annotations
  hitl_approved = true
  label = bad
```

Then run:

```bash
ai-test-evals
```

```
🔄 Syncing Human-in-the-Loop approvals from Phoenix UI...
🎯 Found HITL annotation for Span ID: 3f8a2c...
   Input: "Predict WTI price given 90-day window with geopolitical event flag"
   Issue: Model did not account for supply shock in feature set
🚀 LLM distilling failure pattern...
   → Rule: "Prediction agent must include geopolitical_event_flag as a feature input when available in the ingestion dataset."
✅ Golden dataset updated: case_004 added
✅ Custom judge criteria updated (8/10 rules)

🎯 Running regression scorecard...
   Correctness: 91% ✅  |  Tool Accuracy: 96% ✅  |  Latency: nominal ✅
```

The rule is now enforced on every future PR. The next developer who touches the prediction agent will be blocked by CI if they remove the geopolitical event flag — the system learned from the real-world failure and codified it automatically.

---

## Key Commands

| Command | What it does |
|---|---|
| `ai-mode-local` | Switch to 100% offline Ollama mode |
| `ai-mode-hybrid` | Switch to cloud frontier mode |
| `ai-stack-off` | Disable all hooks (corporate / clean mode) |
| `ai-stack-check` | Health check: Phoenix, Ollama/API keys, unresolved log entries |
| `ai-stack-status` | Current mode, muted flag, network connectivity |
| `ai-dashboard-start` | Start Arize Phoenix at localhost:6006 |
| `ai-dashboard-stop` | Stop Phoenix |
| `ai-test-evals` | Sync HITL feedback + run eval scorecard |
| `ai-stack-promote <id> <query> <output>` | Promote a production fix to the golden dataset |
| `ai-stack-scrub [dir]` | Remove runtime artefacts from a project directory |

---

## Prerequisites

| Requirement | Version |
|---|---|
| macOS / Linux / Windows | — |
| Python | 3.11+ |
| Git | 2.x |
| Ollama *(local mode only)* | Latest |
| Docker *(team Phoenix only)* | 20+ |
| Node.js *(TS/React projects)* | 20+ |
| Go *(Go projects)* | 1.22+ |

---

## Configuration

All configuration is via environment variables in `~/.zshrc` — no config files to edit manually.

| Variable | Default | Purpose |
|---|---|---|
| `AI_STACK_MODE` | `local` | `local` / `hybrid` / `disabled` |
| `AGENT_OWNER_ID` | — | Your email — ties all traces to you |
| `AGENT_OWNER_NAME` | — | Your display name |
| `AGENT_JUDGE_MODEL` | `claude-sonnet-4-6` | LLM used for eval scoring — change without editing code |
| `AGENT_PHOENIX_ENDPOINT` | `http://localhost:6006` | Phoenix URL (local or team-shared) |
| `OPENAI_API_KEY` | — | Required for hybrid mode |
| `ANTHROPIC_API_KEY` | — | Required for hybrid mode |
| `OS_LLM_BASE_URL` | `http://localhost:11434/v1` | Open-source LLM endpoint |
| `AI_STACK_SLACK_WEBHOOK` | — | Slack alerts on failover / budget breach |
| `AI_STACK_TEAMS_WEBHOOK` | — | MS Teams alerts |

---

## Beyond Solo Dev: Multi-Tenant, Production, and Enterprise

Everything above is the single-developer dev-mode path. The framework also
has a production/multi-tenant layer, built and tested against real
infrastructure (Postgres, Redis, Temporal, Kubernetes, a live OIDC provider):

| Layer | What it adds |
|---|---|
| **Multi-Tenancy** | `ai-tenant-init` / `ai-tenant-promote` scaffold an independent tenant repo with its own CI/CD, eval gates, and `staging → production` promotion flow (exact-match tenant-id guard, not substring) |
| **Production Runtime** | `runtime/llm_gateway.py` (atomic per-tenant budget reservation + degrade ladder), `runtime/trace_redactor.py` (per-span tenant-bound redaction), `runtime/idempotency.py` + `runtime/dead_letter.py` (Postgres/Redis-backed, not stubs — idempotency has no in-memory fallback, so without `REDIS_URL`/`DATABASE_URL` the gateway degrades to no duplicate-call suppression rather than failing), Temporal workflow patterns in `runtime/workflows/` — including `run_with_recoverable_step`, which parks a failed workflow *alive* (not dead-lettered) so a human can edit the failing payload in the Ops Portal and resume it in place. Cloud-native model hosting (GCP Vertex AI, Azure OpenAI, AWS Bedrock, Huawei ModelArts) is supported via `CloudProviderAdapter`s in `runtime/provider_dispatch.py` — GCP Vertex AI is live-verified end-to-end (`vertex_gemini` role in `models.yaml`); Azure OpenAI, Bedrock, and Huawei ModelArts remain mock-tested only (SPECS.md §29 "Cloud-Native Provider Adapters") |

`BUDGET_BACKEND` selects which of these the gateway's per-tenant budget store uses (`runtime/llm_gateway.py:_make_budget_backend`):

| | Dev (`memory`, default) | Prod (`postgres`) | Prod (`redis`) |
|---|---|---|---|
| Scope | Single process | Cross-process / cross-worker | Cross-process / cross-worker |
| Setup | None — works out of the box | `DATABASE_URL`, already provisioned for the Ops Portal | `REDIS_URL`, separate service if not already running |
| Durability | Lost on process restart | WAL-backed, durable | In-memory unless persistence configured |
| Atomic reserve | Lock-guarded dict add | `UPDATE ... WHERE spent_usd + $1 <= cap` | `INCRBYFLOAT` + compensating rollback on overshoot |
| Queryability | None | SQL-joinable with `agent_runs`, audits | Key-value only |
| Best for | Local dev, unit tests, CI | Multi-worker fleets, especially if Postgres is already running for the portal | Multi-worker fleets needing the lowest-latency reserve path, or where Redis is already in use |
| **Ops Portal** | `portal/` — role-based access control (viewer/operator/admin, per-tenant scoped), cross-tenant cost/issues dashboard with real run status and Phoenix error rate, per-tenant DLQ triage (edit payload, Replay/Discard), history sync, HMAC-signed tamper-evident audit log, SSO/OIDC login with server-side session revocation |
| **On-Premise Deployment** | `templates/onprem-deploy/` — opt-in Docker Compose or Helm chart for air-gapped/on-prem customers, with canary + shadow traffic routing (Traefik or Envoy, customer's choice) |
| **In-App Widget** | `templates/in-app-widget/` — embeddable end-user status component, token-scoped, no cross-tenant access; self-hosted (ships as a release asset, no CDN dependency) |
| **Enterprise Pack** | `enterprise/` — GPG-signed hook bundles + MDM deployment, HMAC-validated break-glass bypass tokens with expiry, developer opt-in + RFC-enforcement git hooks, dedicated per-tenant Kubernetes worker pools |

### UAE / sovereign compliance (differentiator)

UAE deployments need more than a global SaaS chatbot: **in-border
inference**, **bias accountability**, **HITL stop-gates**, **PDPL-aligned
PII handling**, and **governance embedded in the architecture** (including
alignment toward ISO/IEC 42001 and oversight expectations). AgentSmith maps
each mandate to concrete runtime controls — local/on-prem + pluggable
Falcon/UAE endpoints, HITL gates, redaction, audit artifacts — and tracks
remaining gaps in FIXES.

See **[docs/uae-regulatory.md](./docs/uae-regulatory.md)** for the full
Rule / Action / AgentSmith status map (not legal advice or certification).

See **[OPERATIONS.md](./OPERATIONS.md)** for the full step-by-step: install, run, test every feature, run evals, deploy to production through GitHub CI/CD, and monitor operations.

---

## Documentation

- **[SPECS.md](./SPECS.md)** — Full formal specification: all pillars, components, data schemas, decision log
- **[UserManual.md](./UserManual.md)** — Day-to-day usage for solo/team dev mode: commands, workflows, maintenance
- **[OPERATIONS.md](./OPERATIONS.md)** — Step-by-step install/config/test/operate, including multi-tenancy, production runtime, Ops Portal, and the enterprise pack
- **[docs/uae-regulatory.md](./docs/uae-regulatory.md)** — UAE sovereign / PDPL / HITL / fairness / ISO 42001 mapping (differentiator)

---

## Repository Structure

```
AgentSmith/
├── install-ai-stack.sh        # Entry point — run this once
├── scripts/                   # Python agent stack (dev lifecycle) + generate-ide-config.py
├── runtime/                   # Production runtime — llm_gateway, trace_redactor, worker, workflows/, k8s/
├── hooks/                     # Git hook templates
├── templates/                 # IDE config source of truth (agent-rules.yaml) + in-app-widget/
├── portal/                    # Ops Portal (Next.js)
├── enterprise/                # Org hook bundle signing, MDM deploy, bypass policy
├── examples/oil-price-agent/  # Reference tenant app (fork per customer, never deploy from here)
├── fixtures/                  # Baseline golden dataset + judge criteria
├── docs/                      # Topic docs (e.g. uae-regulatory.md)
├── caddy/                     # Phoenix auth sidecar config
├── docker-compose.yml         # Team-shared Phoenix + PostgreSQL
├── docker-compose.auth.yml    # Optional overlay: HTTP basic auth in front of Phoenix
├── .github/workflows/         # Framework's own CI + release pipeline
├── Readme.md
├── SPECS.md
├── UserManual.md
└── OPERATIONS.md
```

---

## License and Trademark

This project is released under the [MIT License](./LICENSE).

The name **AgentSmith**, the AgentSmith logo, and associated marks are
subject to trademark protections. Use of these marks in your own products,
services, or distributions requires explicit written permission. See
[TRADEMARK.md](./TRADEMARK.md) for permitted uses, restrictions, and
attribution guidelines.
