# AgentSmith — Formal Specification

**Version:** 0.5.0-draft
**Date:** 2026-06-23
**Status:** Draft — incorporates tenancy, production runtime, observability review, and the security/correctness fix pass tracked in `FIXES_AND_CLEANUP.md`

---

## 1. Purpose

AgentSmith is a two-layer package that provisions the complete lifecycle environment for AI agents.

**Layer 1 — Dev Lifecycle (workstation):** IDE guardrails, git hooks, local/hybrid LLM routing, PR evaluations, Knowledge Graph, self-improvement loop. Installed once per developer machine or team server.

**Layer 2 — Production Runtime (cloud):** Durable workflow orchestration, tenant-scoped deployment, LLM gateway with per-tenant budget enforcement, environment-aware trace redaction, ops portal.

> AgentSmith equips each tenant application to deploy itself. It does not deploy customer applications from a shared platform repository.

Installed once (developer mode) or deployed as org bundle (enterprise mode), it sets up:

- IDE rules and guardrails for Cursor, Claude Code, and Antigravity (`CLAUDE.md`, `.cursorrules`, `.agents/skills/`)
- Git lifecycle hooks (pre-commit, commit-msg, post-commit, post-checkout) — opt-in per repo (developer mode) or org-managed signed bundle (enterprise mode)
- A universal observability platform (Arize Phoenix) with per-project and per-tenant namespacing
- An evaluation framework with golden datasets and an LLM-as-judge; framework base cases are **bootstrap-only**; production quality gates use tenant-local datasets exclusively
- A multi-agent orchestration layer (LangGraph for dev, Temporal/Celery for production)
- A codebase Knowledge Graph (AST-driven, auto-updating, strictly per-repository)
- A self-improvement loop with Human-in-the-Loop (HITL) promotion
- A financial circuit breaker with tiered degrade (dev: session-scoped; production: LLM Gateway-enforced per tenant)
- Automated CI/CD pipelines via GitHub Actions — per tenant repo, per environment
- Tenant scaffold tooling (`ai-tenant-init`, `ai-tenant-promote`)
- Three observability surfaces: Phoenix traces/evals/HITL, Ops Portal (cross-tenant ops), In-App Widget (end-user status)

### Implementation Status Against This Vision

Everything in the list above is implemented and verified against real
infrastructure (Postgres, Redis, a real OIDC provider, `kind` Kubernetes,
real GPG keys) — see `FIXES_AND_CLEANUP.md` for the line-by-line audit
trail. Specifically real, not aspirational:

- Dev lifecycle layer (hooks, IDE rules, Knowledge Graph, dev-mode LLM routing, eval gate)
- Production LLM Gateway with atomic per-tenant budget enforcement and a degrade ladder
- Environment-aware trace redaction with per-span tenant binding and encrypted HITL blobs
- Idempotency store and dead-letter queue (Postgres-backed; see §25)
- Ops Portal with role-based access control, signed/tamper-evident audit log, SSO session revocation
- Enterprise pack: signed hook bundles, HMAC-validated break-glass tokens, developer opt-in + RFC enforcement gates

Additionally implemented and verified against live infrastructure (same bar as above):

- CD → Ops Portal history sync (`scripts/sync-portal-history.py`, wired into `cd-staging.yml`/`cd-production.yml` — §26)
- Shadow eval sampler (`scripts/shadow-eval.py` — samples 5% of production spans, judges async, writes Phoenix annotations, surfaces suggested promotions in the Ops Portal — §9). **CI approach:** `shadow-eval.yml` is schedule-only (opt-in nightly cron, never per-PR — a live tenant Phoenix isn't available in that context); CI coverage comes from `scripts/test/test_shadow_eval.py` (sampling determinism, judge-prompt shape) wired into `self-test.yml`'s `python-behaviour` job.
- Ops Portal v2: real `agent_runs` table with `running`/`success`/`degraded`/`failed` aggregation per workflow, cost cap from `tenant.yaml`, Phoenix 24h trace count + error rate via GraphQL — §26, §29
- CD deploy/rollback automation: composite actions (`.github/actions/deploy-placeholder/`, `.github/actions/rollback-notify/`) + GHCR image build; rollback posts to Slack/Teams and fails the job whether or not a `ROLLBACK_COMMAND` is set — tenants supply the real command, the notification and job-failure are mandatory — §22
- GCP CI/CD end-to-end: `.github/actions/gcp-auth` composite action (Workload Identity Federation, keyless) verified through real GitHub Actions runs deploying both `bobbyaqlaar/oil-price-demo` (worker) and `bobbyaqlaar/AgentSmith` Ops Portal to Cloud Run on GCP project `agentsmith-500916` (2026-07-01). `.github/actions/build-push-ghcr` + Artifact Registry re-push pattern verified. `cd-portal.yml` added for the Ops Portal (Next.js → Cloud Run via AR).

**Genuine remaining gaps** (not yet built — trigger conditions documented in
`FIXES_AND_CLEANUP.md` "Future Phases"): short-term conversation memory,
vector store retrieval, `@tool` registration/schema-extraction, LLM-driven
self-correction, pre-call input guardrails, hallucination-rate metric, TTFT
tracking (requires streaming support), fairness/robustness evaluation. None
of these are regressions — they were evaluated and deliberately deferred
pending a concrete tenant call site to design against.

---

## 2. Guiding Principles

| Principle | Description |
|---|---|
| **Ponytail** | Prefer native platform libraries over custom abstractions. Minimize third-party dependency trees. |
| **Caveman Compression** | Agents output code and data directly. No pleasantries, summaries, or explanatory chat. |
| **March of Nines** | Zero tolerance for swallowed errors, empty catch blocks, loose timeouts, or missing edge-case handling. |
| **Headroom** | Context windows must be kept lean. Use Knowledge Graph subgraph extraction rather than loading full files. |
| **HITL** | Human approval is required before any distilled production lesson is promoted to the golden dataset or judge criteria. |
| **Tenant Isolation** | Each customer application is an independent repository with isolated promotion tracks, eval suites, config, and runtime partition key (`tenant.id`). |
| **Environment Safety** | Trace and log content policy varies by `$ENVIRONMENT`; production never stores raw secrets or PII in observability backends by default. |
| **Durable Execution** | Production agent workflows must survive process crash, deploy, and network failure via external checkpointing and idempotent activities. |
| **Framework ≠ Application** | AgentSmith releases on its own semver; tenant apps pin and upgrade independently. |

---

## 3. System Architecture

### Layer 1 — Developer Workstation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Developer Workstation                           │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Shell Profile (~/.zshrc)                                        │  │
│  │  ai-mode-local | ai-mode-hybrid | ai-stack-check                 │  │
│  │  ai-dashboard-start | ai-test-evals | ai-stack-promote           │  │
│  │  ai-tenant-init | ai-tenant-promote | ai-stack-upgrade           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────┐   ┌───────────────────┐   ┌───────────────────────┐  │
│  │  Git Hooks   │   │  IDE Rules        │   │  Agent RFC Dir        │  │
│  │  pre-commit  │   │  .cursorrules     │   │  .agent-rfc/          │  │
│  │  commit-msg  │   │  CLAUDE.md        │   │  fixtures/            │  │
│  │  post-commit │   │  .agents/skills/  │   │  golden_evals.json    │  │
│  │  post-chkout │   │  agent-rules.yaml │   │  custom_judge.json    │  │
│  └──────┬───────┘   └───────────────────┘   │  knowledge_graph.json │  │
│         │                                   │  token_velocity.json  │  │
│         │ triggers                          └───────────────────────┘  │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Python Agent Stack (scripts/)                                   │  │
│  │                                                                  │  │
│  │  map_codebase.py  ──► local_knowledge_graph.py                  │  │
│  │  multi_agent_system.py / local_agent_stack.py                   │  │
│  │  cost_router.py ──► network_watchdog.py                         │  │
│  │  agent_logger.py ──► circuit_breaker.py ──► notifier.py         │  │
│  │  run-evals.py ──► promote-learning.py ──► sync-ui-feedback.py   │  │
│  │  verify_system.py                                               │  │
│  └─────────────────────────────────┬────────────────────────────────┘  │
│                                    │ OTel OTLP                          │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Arize Phoenix (localhost:6006)                                 │   │
│  │  Trace Dashboard | Experiment Scorecards | HITL Annotations     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌───────────────────┐      ┌───────────────────────────────────────┐  │
│  │  Local GPU (Ollama│      │  Cloud Frontier (Hybrid Mode)         │  │
│  │  llama3 / mistral │  OR  │  Claude 3.5 Sonnet / GPT-4o / Groq   │  │
│  │  gemma2           │      │  + cost_router.py heuristics          │  │
│  └───────────────────┘      └───────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ OTel contract + agent identity + tenant.id
                                   ▼
```

### Layer 2 — Production Runtime (Cloud)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Production Runtime                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Workflow Engine (Temporal preferred / Celery+Redis fallback)   │   │
│  │  • Durable workflows with idempotency keys                      │   │
│  │  • Dead-letter queue on activity failure                        │   │
│  │  • HITL pause/resume via workflow signals                       │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                  │                                      │
│  ┌───────────────────────────────▼──────────────────────────────────┐  │
│  │  Worker Pool  (runtime/worker.py)                                │  │
│  │  • Partitioned by tenant.id                                      │  │
│  │  • Shared pool (default) | Dedicated pool (isolation: dedicated) │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
│                                  │                                      │
│  ┌───────────────────┐   ┌───────▼────────────────────────────────┐   │
│  │  LLM Gateway      │   │  Ops Portal  (portal/)                 │   │
│  │  (runtime/        │   │  • Multi-tenant pipeline view          │   │
│  │   llm_gateway.py) │   │  • Cost by tenant/agent/model          │   │
│  │  Per-tenant budget│   │  • Queue depth, unresolved issues      │   │
│  │  Degrade ladder   │   │  • Suggested HITL promotion queue      │   │
│  └───────────────────┘   └────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Phoenix (Federated — filterable by tenant.id)                  │   │
│  │  • Ops traces | Per-tenant evals | HITL annotations             │   │
│  │  • Auth required in team/production deployment                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

Production runtime components are defined in Section 25. The OTel contract (span attributes, `tenant.id`, `agent.owner_id`, `project.name`) is the interface between Layer 1 and Layer 2.

---

## 4. Ten Operational Pillars

### Pillar 1 — Requirements & Design

**Purpose:** Prevent code generation before a written specification exists.

- An `.agent-rfc/` directory must exist in every repository.
- Agents are forbidden from modifying source files unless a markdown spec exists in `.agent-rfc/`.
- Before any code change, the agent must produce a step-by-step implementation blueprint mapped to a spec file.
- Spec files follow: `NNN-<slug>.md` (e.g., `001-auth-fix.md`).
- **Enterprise mode (hook enforcement):** Staged source changes must map to an open RFC file in `.agent-rfc/`, or the commit message must include an `RFC-NNN` reference resolvable to a spec. Violation blocks the commit. This rule is enforced at the hook level — IDE instructions alone cannot guarantee compliance.

### Pillar 2 — Build Architecture (Ponytail)

**Purpose:** Enforce minimal, native-first implementations.

- Run a 5-step analysis before creating new files: (1) does this already exist? (2) is there a native library? (3) what is the minimal change? (4) what does this affect? (5) are there downstream graph dependencies?
- Forbidden: unapproved third-party dependencies, over-engineered wrapper components, or custom abstractions over standard library functionality.
- New files must be registered in the Knowledge Graph before creation.

### Pillar 3 — Tracing & Evaluations (Observability)

**Purpose:** Make every token, tool call, and latency metric visible — with environment-appropriate content capture.

All agent execution must emit OpenTelemetry spans to `$AGENT_PHOENIX_ENDPOINT/v1/traces`.

**Span content policy by environment:**

| Environment | `input.value` / `output.value` | Other sensitive attributes |
|---|---|---|
| `development` | Full capture (up to 1,000 chars) | Unrestricted |
| `staging` | Redacted — secrets/PII patterns stripped; structure preserved | Hashed identifiers |
| `production` | Minimal — hashed or truncated; full payload only in encrypted HITL blob when case is opened | Minimal metadata only |

Every span must carry at minimum: `agent.name`, `agent.role`, `agent.owner_id`, `tenant.id`, `llm.model_name`, `project.name`, `environment`.

If Phoenix is unreachable, log MINOR to `.agent-history.log` and continue — never fail silently. See Section 27 for trace redaction implementation.

### Pillar 4 — Testing Guardrails

**Purpose:** Ensure every change has paired tests and CI enforcement.

- Every logical change requires a corresponding unit or integration test.
- Existing regression tests must never be cleared or skipped to force green coverage.
- Stack-specific CI workflows auto-generated in `.github/workflows/`. See Section 17.

### Pillar 5 — Operations & Self-Improvement

**Purpose:** Build a persistent, bounded memory of production failures and successes.

- `.agent-history.log` in every repository root captures timestamped events.
- On initialization, agents read `.agent-history.log` to avoid repeating past mistakes.
- After two consecutive identical tool failures, the agent appends a MAJOR trace to `.agent-history.log`, halts, and escalates to the user.
- MAJOR/CRITICAL entries are synced to the Ops Portal unresolved queue; teams cannot rely on each developer running `ai-stack-check` locally.
- The HITL promotion loop (`promote-learning.py`) distills raw incidents into atomic rules, appends them to judge criteria, and adds a verified test to `golden_evals.json`.
- Judge criteria use semantic deduplication and versioned archival — no silent FIFO eviction. See Section 9.

### Pillar 6 — Interface Constraints (Caveman Compression)

**Purpose:** Eliminate noise from agent output.

- Agents must not output polite commentary, introductory preambles, or meta-summaries.
- Output must be: code blocks, data structures, terminal commands, and variables only.
- This constraint is injected into `.cursorrules`, `CLAUDE.md`, and Antigravity skills. The single-source template is `templates/agent-rules.yaml`; IDE-specific files are generated from it by the `post-checkout` hook.

### Pillar 7 — Stack-Specific Rules

Injected automatically based on detected project type:

| Stack | Detection | Key Rules |
|---|---|---|
| TypeScript/React | `package.json` present | No `any` type; enforce `'use client'` on client components |
| Python/FastAPI | `requirements.txt` / `pyproject.toml` | Pydantic V2 for all models; async-safe, no blocking calls |
| Go | `go.mod` present | Always check `if err != nil`; table-driven tests; `-race` flag |

Rules are generated from `templates/agent-rules.yaml` and written to: `.cursorrules` (Cursor), `CLAUDE.md` (Claude Code), and `.agents/skills/efficiency_stack/skill.md` (Antigravity).

### Pillar 8 — Observability Wire

**Purpose:** Ensure IDE-level agent requests are routed to the trace collector.

- `.cursorrules` and `CLAUDE.md` include explicit OTLP endpoint instructions.
- `OTEL_EXPORTER_OTLP_ENDPOINT` is set in the shell session when the dashboard starts.

**Data locality clarification:**

| Data type | Dev (local mode) | Dev (hybrid mode) | Production |
|---|---|---|---|
| **Trace data** | Stored at `AGENT_PHOENIX_ENDPOINT` (local or team server) | Stored at `AGENT_PHOENIX_ENDPOINT` | Stored at `AGENT_PHOENIX_ENDPOINT` |
| **Inference data** | Stays on machine (Ollama) | **Transmitted to cloud LLM providers** | Routed via LLM Gateway |

In hybrid mode, prompts and completions are transmitted to cloud provider APIs (Anthropic, OpenAI, Groq). Trace data remains at the configured Phoenix endpoint.

### Pillar 9 — Multi-Agent Orchestration

**Purpose:** Enable stateful, multi-step agent workflows with guardrailed handoffs.

| Context | Backend | Checkpointer |
|---|---|---|
| Dev / IDE sessions | LangGraph ≥0.2 + `MemorySaver` OR `local_agent_stack.py` | In-memory (acceptable for dev) |
| Production | Temporal workflow (preferred) or Celery+Redis task chain | Postgres (Temporal) or Redis — **MemorySaver prohibited in production** |

Three-node topology: Architect → Developer → Validator (HITL interrupt on max retries).

Domain agent topologies (e.g., ingestion → prediction → decision → order) are defined **in each tenant repo**, not in the framework. The framework provides reference workflows in `examples/` and `runtime/workflows/`.

### Pillar 10 — Cost-Optimization Routing

**Purpose:** Route tasks to the cheapest capable model.

| Context | Routing mechanism |
|---|---|
| Dev / IDE sessions | `cost_router.py` — keyword + token heuristics |
| Production | LLM Gateway (`runtime/llm_gateway.py`) — per-model pricing, per-tenant budget, degrade path |

`cost_router.py` limitations: not wired into IDEs, uses brittle heuristics, no per-model accurate accounting. Acceptable for dev sessions; inadequate for production multi-tenant cost control.

Production degrade path: throttle rate → downgrade model tier → queue with delay → halt cloud inference (local fallback if available) → alert via Ops Portal + Slack/Teams.

---

## 4a. Architecture by Layer

§4's Ten Pillars are this framework's own operational guardrails. This
section is a different, complementary cut: the **functional and
non-functional layers** any agentic application needs, each mapped to the
§-numbered section below that specifies it precisely, plus what's
genuinely not built and why a particular alternative wasn't chosen where
that decision has already been made. Read this before re-evaluating a
design choice that's recorded here as settled.

### Functional layers

| Layer | Current state | Detail |
|---|---|---|
| **Reasoning & Planning** | Fixed-topology reference patterns (Architect→Developer→Validator), not a generic planner | §8 (execution modes), §9 (eval framework scores the output of these patterns) |
| **Tool Orchestration** | Activity *execution* + recovery exists (Temporal); tool *registration*/schema-extraction (e.g. an `@tool` decorator) and LLM-driven tool-call selection do not — `llm_gateway.py.complete()` sends a prompt and receives text, no function-calling fields in the provider request | §25 (Production Runtime), §29 (LLM Gateway) |
| **Memory Management** | Partially implemented. **Long-term (structured):** the codebase Knowledge Graph — `map_codebase.py` → `local_knowledge_graph.py`, NetworkX `DiGraph` persisted as JSON node-link, queried via `fetch_subgraph_context_window()`/`impacted_files()` to give a cold session long-term recall over the code (dependencies, guardrails, past incidents — see §10 "Cross-Session Refactoring & Defect-Fixing"). **Absent:** short-term token-window manager (truncation/summarization/sliding-window) and semantic/vector retrieval (Chroma/pgvector/etc.) — the graph is structured lookup, not embedding similarity. Present but distinct: Temporal's durable-execution history (workflow progress, not conversation memory) and LangGraph `PostgresSaver` (dev/hybrid only, `MemorySaver` banned in production) | §10 (Knowledge Graph), §25 "Idempotency Key Design", §8 |
| **Perception & Input Parsing** | Narrow JSON-from-text extraction (`re.search` + `json.loads`, no schema validation) in the reference pipelines; no dynamic prompt-template engine (prompts are inline f-strings) | §8 |
| **Human-in-the-Loop (HITL)** | The most built-out layer — two distinct mechanisms, see §25 "HITL Pause / Resume" for the full approve/reject vs. edit-and-resume split and the recorded reasoning for Temporal signals over Slack+Retool/LangGraph-interrupt alternatives, and for the portal-webhook-bridge design over a direct portal-side Temporal client | §25, §30 (HITL RBAC) |

### Non-functional layers

| Layer | Current state | Detail |
|---|---|---|
| **Observability & Traceability** | Full span attribution (tenant/agent/cost/tokens) via OTel→Phoenix. Time-to-First-Token is NOT tracked — `llm_gateway.py` is non-streaming, so there's no first-token timestamp to record | §15, §29 |
| **Reliability & Accuracy** | `correctness`/`tool_accuracy`/`latency` scored per case (§9) — no metric literally named "hallucination rate" (a hallucination surfaces as low `correctness`, not its own number). Auto-retry is two-tiered: Temporal retries transient failures automatically; `run_with_recoverable_step` deliberately disables that for validation-shaped failures (`RetryPolicy(maximum_attempts=1)`) since they need a *different* payload, not a bare retry. No LLM-driven self-correction loop exists — recovery is always human-driven (DLQ) or Temporal-driven (transient retry), never model-driven | §9, §25 |
| **Security & Guardrails** | Asymmetric: `trace_redactor.py` redacts/anonymizes data **after** a call for observability storage — there is no symmetric **pre-call** PII scrubber or content moderator between user input and the prompt sent to the model | §27 (Trace Redaction) |
| **Explainability** | Infrastructure-level: HMAC-signed, tamper-evident, append-only audit log (§30) + full OTel trace history — not per-decision natural-language reasoning narration | §30, §15 |
| **Scalability & Performance** | Workflow concurrency via Temporal's shared/dedicated worker-pool model (§23, §25); app-version traffic-shaping via on-prem canary routing, customer's choice of Traefik or Envoy (§25 "On-Premise / Air-Gapped Deployment"). TTFT-bounded latency targets are not measurable without adding streaming to the Gateway first (same gap as Observability above) | §23, §25 |
| **Data Bias & Fairness** | Not implemented — no fairness/bias/robustness metric tracked anywhere in the eval framework (§9); a fairness dimension would be new judge criteria and likely a separate dataset, not an extension of the existing correctness-focused golden set | §9 |
| **Continuous Improvement** | Two independent loops: the HITL promotion loop (§9 "HITL Promotion Flow" — human-annotated production traces become golden-dataset cases) and the shadow-eval sampler (§9 — passive 5% production-trace sampling, judged the same way, surfaced as a read-only suggested-promotion queue, never auto-promoting) | §9 |

---

## 5. Component Inventory

### 5.1 Installer

| File | Purpose |
|---|---|
| `install-ai-stack.sh` | Master installer. Writes git hook templates, sets `git config --global init.templateDir`, appends shell functions to `~/.zshrc`. Supports `--mode developer` (default) and `--mode enterprise`. |

**Hook templates** live as standalone files in `hooks/` (repo root) — `install-ai-stack.sh` copies them into `$TEMPLATE_DIR/hooks/`, falling back to a GitHub release download if run outside a local checkout. This is also what `enterprise/package-hook-bundle.sh` signs for org bundle distribution (see §22, §30).

### 5.2 Git Hooks (global templates)

| Hook | Trigger | Action |
|---|---|---|
| `pre-commit` | Before every commit | Blocks: unresolved AI markers, empty catch blocks (JS/TS), double blank identifiers (Go). Enterprise mode: also requires `RFC-NNN` reference in commit message or matching RFC file in `.agent-rfc/`. |
| `commit-msg` | Commit message validation | Enforces Conventional Commits: `<type>(<scope>)?: <summary>` (max 72 chars) |
| `post-commit` | After every commit | Runs `map_codebase.py`; auto-tags semver; appends to `.agent-history.log`; pushes tags if remote tracked; runs log rotation |
| `post-checkout` | After branch switch / git init | Detects stack; creates `.agent-rfc/`; generates IDE config from `agent-rules.yaml`; writes CI workflows; seeds golden dataset |

### 5.3 IDE Configuration Files (auto-generated per repo)

Generated by `post-checkout` hook from `templates/agent-rules.yaml` (single source of truth).

| File | Contents |
|---|---|
| `.cursorrules` | 10-pillar system rules, stack addendum, OTLP endpoint |
| `CLAUDE.md` | Claude Code session start checklist, test command, RFC compliance, HITL escalation |
| `.agents/skills/efficiency_stack/skill.md` | Antigravity lifecycle guardrails skill |
| `.agents/skills/observability/skill.md` | OTel span emission instructions |
| `.agents/skills/self_improvement/skill.md` | Log monitoring and HITL escalation |

Note: `.claudecode.json` is deprecated. All Claude Code configuration uses `CLAUDE.md` (the current standard). Any legacy `.claudecode.json` files should be migrated.

### 5.4 Python Agent Stack (scripts/)

| File | Purpose |
|---|---|
| `local_knowledge_graph.py` | NetworkX DiGraph. Loads/saves `.agent-rfc/fixtures/knowledge_graph.json`. API: `inject_production_learning()`, `fetch_subgraph_context_window()` |
| `map_codebase.py` | AST-walks `.py`, `.ts`, `.tsx`, `.go` files. Registers `CodebaseFile` nodes. Purges stale nodes. Extracts guardrails from `.cursorrules` and `.agent-rfc/`. `--quiet` suppresses the summary line for CI usage. |
| `local_agent_stack.py` | Pure-Python multi-agent loop (offline mode). Architect→Developer→Validator via Ollama HTTP. Full OTel span nesting. |
| `multi_agent_system.py` | LangGraph stateful graph (hybrid mode). `MemorySaver` checkpointer — **dev use only**. HITL pause loop. Falls back to `local_agent_stack.py` if LangGraph unavailable. |
| `cost_router.py` | Dev-mode routing: token count + keyword analysis → model selection. Not suitable for production. See §29 for production LLM Gateway. |
| `network_watchdog.py` | Socket ping to `1.1.1.1:53`. Auto-switches active LLM endpoint. Background keepalive thread. |
| `notifier.py` | Cross-platform desktop notifications via `plyer` + `osascript` (macOS). Background webhook thread (Slack / Teams / custom). |
| `run-evals.py` | Loads tenant-local golden dataset. Runs judge scorecard. `--fail-below` flag. Skips gracefully when <3 cases. |
| `promote-learning.py` | Appends to `golden_evals.json`; archives resolution as judge learning (versioned, not FIFO-evicted); marks log entry `hitl_resolved: true` with `hitl_resolved_by` + `hitl_resolved_at`. |
| `sync-ui-feedback.py` | Pulls Phoenix annotations; promotes unsynced negative feedback to golden dataset. |
| `agent_logger.py` | JSON-Lines to stdout + `.agent-history.log`. Four levels: INFO/MINOR/MAJOR/CRITICAL. Calls `audit_token_velocity_circuit()`. All entries carry `owner_id`, `tenant.id` (if available), `agent.role`. |
| `circuit_breaker.py` | Dual-tier burst/monthly guard. Dev-mode: raises `CircuitBreakerTripped`. Production: degrade ladder via LLM Gateway (see §11, §29). |
| `verify_system.py` | Full health check: Python, packages, hooks, Phoenix, Ollama, identity, unresolved issues. CI flags: `--check-hooks`, `--check-redaction`, `--check-idempotency`, `--check-dlq`, `--check-history-sync`, `--check-onprem-deploy`, `--check-kg` (rebuilds the Knowledge Graph via `map_codebase.py` and asserts it is non-empty with the known `scripts/` nodes — Pillar 2 / FIXES_AND_CLEANUP.md P10a). |
| `generate-ide-config.py` | Renders `.cursorrules` / `CLAUDE.md` / `.agents/skills/*/skill.md` from `templates/agent-rules.yaml` (single source, §13). Called by `post-checkout`. `--check-only` regenerates in memory and diffs against the committed files, exiting 1 on drift (Pillar 6/7 CI gate — FIXES_AND_CLEANUP.md P10c). |

### 5.5 Production Runtime (runtime/)

See Section 25 for full specification. Stub implementations in `runtime/`.

| File | Purpose |
|---|---|
| `runtime/worker.py` | Temporal/Celery worker entrypoint. Partitioned by `tenant.id`. |
| `runtime/llm_gateway.py` | Production LLM routing with per-model pricing, per-tenant budget enforcement, degrade ladder. |
| `runtime/trace_redactor.py` | Environment-aware OTLP span scrubbing before export. |
| `runtime/idempotency.py` | Idempotency key store and deduplication. |
| `runtime/dead_letter.py` | Failed task queue and replay API. |
| `runtime/workflows/` | Reference durable workflows (tenant repos own their production definitions). |

### 5.6 Observability Surfaces

| Path | Purpose |
|---|---|
| `portal/` | Ops dashboard (Next.js or equivalent). Multi-tenant pipeline view, cost, queue depth, unresolved issues, HITL promotion queue. SSO/OIDC when enterprise pack enabled. |
| `templates/in-app-widget/` | Embeddable component (React/Vanilla). Shows last agent run status, tenant-scoped trace link, error summary. Read-only; tenant-scoped auth. |

### 5.7 Data Files

| Path | Schema | Notes |
|---|---|---|
| `.agent-rfc/NNN-<slug>.md` | Free-form markdown spec | Required before any code change |
| `.agent-rfc/fixtures/golden_evals.json` | `[{id, input, expected_tool, reference_output}]` | **Tenant-local only**; seeded from bootstrap base; grows via HITL |
| `.agent-rfc/fixtures/custom_judge_criteria.json` | `{name, version, instructions, historical_learnings: [str]}` | Versioned; semantic dedup; evicted rules archived to `.archive.json` |
| `.agent-rfc/fixtures/knowledge_graph.json` | NetworkX `node_link_data` JSON | Auto-updated by `map_codebase.py` on every commit/checkout |
| `.agent-rfc/fixtures/token_velocity_cache.json` | `{config, monthly_accumulated_spend_usd, current_month_identifier, events}` | Dev session budget; monthly auto-reset |
| `.agenticframework/tenant.yaml` | Tenant config schema | See Section 23 |
| `.agent-history.log` | JSON-Lines; `MAJOR`/`CRITICAL` never pruned until `hitl_resolved: true` | Synced to Ops Portal unresolved queue |

---

## 6. Shell Command Interface

All commands are Zsh/Bash functions in `~/.zshrc`.

### Environment Control

| Command | Action |
|---|---|
| `ai-mode-local` | Sets `AI_STACK_MODE=local`. Runs health check. Fires desktop notification on success. |
| `ai-mode-hybrid` | Sets `AI_STACK_MODE=hybrid`. Runs health check. Fires desktop notification. |
| `ai-stack-off` | **Developer mode only:** Sets `DISABLE_AI_STACK=true`, unlinks `init.templateDir`. Hooks silently exit. **Enterprise mode:** Disabled. Emergency bypass requires IT break-glass procedure with audit log entry. |
| `ai-stack-status` | Prints: mode, muted flag, Phoenix endpoint, judge model, network status, owner identity. |

### Health & Diagnostics

| Command | Action |
|---|---|
| `ai-stack-check` | Checks Phoenix; Ollama (local mode) or API keys (hybrid); surfaces unresolved MAJOR/CRITICAL log entries for current project. |

### Dashboard

| Command | Action |
|---|---|
| `ai-dashboard-start` | Starts Phoenix on `$AGENT_PHOENIX_PORT`. Sets `OTEL_EXPORTER_OTLP_ENDPOINT`. |
| `ai-dashboard-stop` | Stops Phoenix. Unsets OTel env vars. |

### Evaluation & Self-Improvement

| Command | Action |
|---|---|
| `ai-test-evals` | Syncs Phoenix annotations (`sync-ui-feedback.py`), then runs scorecard (`run-evals.py`). Starts dashboard if offline. |
| `ai-stack-promote <id> <query> <output>` | Calls `promote-learning.py`. Re-runs evals to validate fix. |

### Tenant Lifecycle

| Command | Action |
|---|---|
| `ai-tenant-init <id> [--stack STACK]` | Scaffolds tenant repo with `.agenticframework/tenant.yaml`, per-env CI/CD workflows, and metadata. |
| `ai-tenant-promote <id> --from <env> --to <env>` | Promotes deployment within **same tenant repo** (e.g., staging → production). No cross-tenant promotion. |

### Maintenance

| Command | Action |
|---|---|
| `ai-stack-upgrade [--to VERSION]` | Upgrades vendored framework scripts in current repo to pinned version. |
| `ai-stack-scrub [dir]` | Interactive confirmation. Removes framework runtime artefacts from target directory. |
| `ai-stack-uninstall` | Enterprise-safe removal of machine-level install. Restores `git templateDir` to previous value. |

---

## 7. Installation Procedure

### Install Modes

| Mode | Audience | Hook behaviour | Bypass policy |
|---|---|---|---|
| `developer` (default) | Solo / small team | Opt-in per repo via `.agenticframework/enabled`; global `init.templateDir` | `DISABLE_AI_STACK=true` or `ai-stack-off` |
| `enterprise` | Org-managed | IT-deployed signed bundle; hooks pushed via MDM; no global `init.templateDir` mutation | IT break-glass only; bypass is audited |

```bash
./install-ai-stack.sh --mode developer   # default
./install-ai-stack.sh --mode enterprise  # org bundle; no global git config mutation
```

### Prerequisites

| Requirement | Version |
|---|---|
| macOS or Linux | macOS 12+ / Ubuntu 22+ |
| Python | 3.11+ |
| Git | 2.x |
| Zsh or Bash | Default on macOS / any Linux |
| Ollama (local mode only) | Latest |
| Node.js (for TS/React projects) | 20+ |
| Docker (team-shared Phoenix) | Latest |

### Installation Steps

```bash
# 1. Run the master installer
chmod +x install-ai-stack.sh
./install-ai-stack.sh

# 2. Reload shell and activate
source ~/.zshrc
ai-mode-local    # 100% offline via Ollama
# OR
ai-mode-hybrid   # Cloud frontier APIs

# 3. Start the trace dashboard
ai-dashboard-start

# 4. Apply to a project
cd /path/to/your/project
git init   # triggers post-checkout hook

# 5. Verify
python3 scripts/verify_system.py
```

### Enterprise Org Bundle Delivery

Enterprise install produces:
- Signed hook tarball: `agenticframework-hooks-<version>.tar.gz` (SHA-256 verified)
- MDM deploy script template for IT
- Org policy file `agenticframework-org.yaml`: hook version pin, bypass policy, Phoenix endpoint, SSO config

For internal registries, the installer supports fetching from a private artifact store:

```bash
./install-ai-stack.sh --registry https://artifacts.yourcompany.com
```

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `AI_STACK_MODE` | `local` / `hybrid` / `disabled` | `local` |
| `DISABLE_AI_STACK` | `true` / `false` — mutes hooks (developer mode only) | `false` |
| `OS_LLM_BASE_URL` | Open-source LLM endpoint | `http://localhost:11434/v1` |
| `OPENAI_API_KEY` | Required for hybrid mode | `sk-...` |
| `ANTHROPIC_API_KEY` | Required for hybrid mode | `sk-ant-...` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Set by `ai-dashboard-start` | `http://localhost:6006/v1/traces` |
| `AGENT_JUDGE_MODEL` | LLM judge; no code change required | `claude-3-5-sonnet-20241022` (default) |
| `AGENT_OWNER_ID` | Real user identity | `bobby@example.com` |
| `AGENT_OWNER_NAME` | Display name | `Bobby Rajagopal` |
| `AGENT_PHOENIX_ENDPOINT` | Phoenix URL | `http://localhost:6006` |
| `AGENT_MONTHLY_USD_CAP` | Dev session monthly budget. Also the production `LLMGateway`'s fallback budget cap (`runtime/llm_gateway.py:LLMGateway.__init__`) when a tenant doesn't pass an explicit `budget_cap_usd` — same env var, same default, both layers | `150.0` |
| `AI_STACK_SLACK_WEBHOOK` | Optional Slack alert webhook | `https://hooks.slack.com/...` |
| `AGENT_NOTIFY_WEBHOOK` | Generic notification webhook | `https://...` |

---

## 8. Multi-Agent Execution Modes

### Local Offline Mode

- All LLM calls → Ollama at `http://localhost:11434/v1`
- Architect: Mistral; Developer: Llama3; Validator: pure Python logic
- Zero API cost; Apple Silicon GPU accelerated
- Full OTel trace coverage

### Hybrid Cloud Mode

- Architect: Claude 3.5 Sonnet (complex design tasks)
- Developer: GPT-4o or Groq Llama3-70b (via `cost_router.py`)
- Fallback: automatic on network drop (watchdog detects socket timeout)
- **Trace data:** Stored at `AGENT_PHOENIX_ENDPOINT` (local or team server)
- **Inference data:** Prompts and completions are transmitted to cloud provider APIs — they do not stay on the machine

### Production Mode (tenant cloud)

- Workflow engine: Temporal (recommended) or Celery + Redis
- Checkpointer: Postgres (Temporal) or Redis; **`MemorySaver` is prohibited in production**
- Scheduling: per-tenant cron defined in tenant repo config
- HITL pause: workflow signal + Phoenix annotation poll with timeout; DLQ on expiry
- Worker isolation: shared pool with `tenant_id` partition; dedicated pool when `tenant.isolation: dedicated`
- LLM routing: all calls via LLM Gateway (`runtime/llm_gateway.py`) — not `cost_router.py`

### Mode Switching Logic

```
Incoming task
    │
    ▼
Is this a production workflow?
    │
    ├─ Yes ──────────────────────────► Temporal/Celery worker
    │                                  LLM Gateway (per-tenant budget)
    │
    └─ No (dev session)
          │
          ▼
    network_watchdog.is_online()
          │
          ├─ AI_STACK_MODE=local ──────────────────► Ollama
          │
          ├─ AI_STACK_MODE=hybrid + online ────────► cost_router → cloud/open-source
          │
          └─ AI_STACK_MODE=hybrid + offline ───────► Ollama fallback + notification
```

---

## 9. Evaluation Framework

### Golden Dataset Lifecycle

The golden dataset serves two roles: dev quality gate and production calibration flywheel. However, **tenant isolation is strict:**

| Phase | Dataset source | Gate behaviour |
|---|---|---|
| Greenfield bootstrap | Copy from `~/.agent-framework/shared/golden_evals_base.json` once | CI skips eval with warning — gate inactive |
| Before staging promotion | Tenant-authored cases required (minimum: 3) | Gate active for staging deploy |
| Production | Tenant-local cases + HITL-promoted cases from **that tenant's** production traces only | Gate active for production deploy |

Framework base cases (`golden_evals_base.json`) are a bootstrap seed only. They are copied once on first checkout and are not merged into production gates. Each tenant's eval suite reflects that project's task distribution exclusively — cross-project or cross-tenant golden dataset sharing is not supported for production gates.

### Eval Thresholds by Environment

| Environment | `--fail-below` | Behaviour on failure |
|---|---|---|
| CI / PR (`development`) | warn below 0.7 | Warning; does not block |
| Staging deploy | 0.75 | Fails job; blocks promotion |
| Production deploy | 0.80 | Fails job; triggers rollback hook |

### Evaluation Pipeline

```
golden_evals.json (tenant-local)
    │
    ▼
run-evals.py (runs cases through LLM judge)
    │
    ▼
LLM Judge (QAEvaluator + custom_judge_criteria.json)
    ├─ Correctness Score
    ├─ Tool Accuracy Rate
    └─ Latency
    │
    ▼
Phoenix /experiments + eval_results.json
```

### LLM Judge Criteria (Versioned)

`custom_judge_criteria.json` schema:

```json
{
  "name": "string",
  "version": "1.0.0",
  "instructions": "string",
  "historical_learnings": ["string"]
}
```

Rules:
- Version is bumped on every criteria change
- Semantic deduplication before append — no duplicate rules
- When the learnings list grows beyond a project-defined cap, evicted rules are archived to `custom_judge_criteria.archive.json` with timestamp and eviction reason — **never silently discarded**

### Shadow Eval (Production)

An async sampler evaluates 5% of production traces post-hoc:
- LLM judge scores sampled spans asynchronously — does not block user-facing workflows
- Results written to Phoenix experiments, tagged with `eval.type: shadow`
- Feeds suggested promotion queue in Ops Portal

**CI approach:** `workflow-templates/shadow-eval.yml` is an opt-in schedule
(nightly cron, never triggered on every PR — a live tenant Phoenix is not
available in generic CI). CI regression coverage for the sampler's own logic
(`scripts/shadow-eval.py`) is provided by `scripts/test/test_shadow_eval.py`
(sampling determinism, correct 5% rate, judge-prompt shape), wired into
`self-test.yml`'s `python-behaviour` job. Running against a real Phoenix
instance is a manual/scheduled-workflow concern, not a per-PR gate.

### HITL Promotion Flow

```
Production failure detected
    │
    ▼
MAJOR/CRITICAL entry in .agent-history.log + Ops Portal queue
    │
    ▼
Human reviews in Phoenix UI or runs:
  ai-stack-promote <id> '<query>' '<correct-output>'
    │
    ▼
promote-learning.py:
  1. Appends to golden_evals.json
  2. Archives resolution as versioned judge learning (not FIFO)
  3. Marks log entry hitl_resolved: true (writes hitl_resolved_by + hitl_resolved_at)
    │
    ▼
ai-test-evals re-runs to validate fix
```

### CD Golden Dataset Commits

Bot commits to golden dataset fixtures must go through a pull request in the tenant repo — not direct push to `main`. Branch protection applies. Remove `[skip ci]` from eval fixture update commits; CI must validate the new cases.

---

## 10. Knowledge Graph

### Graph Ontology

Node types:
- `Guardrail` — system rules (Ponytail, Caveman, March_Of_Nines)
- `CodebaseFile` — source files indexed by AST mapper
- `ProductionIncident` — distilled lessons from `.agent-history.log`

Edge relation types:
- `IMPORTS` — file-to-file import relationship
- `IMPLEMENTS` — file implements guardrail
- `CAUSED_INCIDENT` — file linked to a production incident

### Storage Path

All Knowledge Graph data persists at `.agent-rfc/fixtures/knowledge_graph.json`. This is the canonical path — consistent with other fixture files. The `map_codebase.py` migration note: if a graph exists at the legacy path `.agent-rfc/knowledge_graph.json` (pre-0.4), the `post-checkout` hook moves it to the fixtures location on first run.

### Tenant Scope

The Knowledge Graph is strictly per-repository. There is no cross-tenant graph federation. `AGENT_SHARED_RFC_DIR` is for documentation sharing within a single organisation's workspace only — shared RFC edges do not span tenant repositories.

### Context Extraction

```python
kg.fetch_subgraph_context_window("path/to/target_module.py", hops=2)
# Returns: {anchor, nodes, edges, guardrails, incidents}
# Token budget: ~200 tokens
```

### Role in the Functional Stack — Long-Term Memory

The Knowledge Graph is the **long-term, structured half of Functional Layer 3
(Memory Management)** (see §4). It is not conversation memory and not a vector
store — it is a graph-structured knowledge base over the codebase that
persists across sessions on disk, independent of any one agent run.

### Cross-Session Refactoring & Defect-Fixing

The graph's purpose is to let a session that begins with **no prior context**
(a fresh agent run, a new developer, a CI job) reconstruct enough of the
codebase to change it safely — long-term recall that would otherwise have to
be re-derived by reading the whole tree, or would simply be lost when the
session that learned it ended.

| Task from a cold session | Graph query | What it prevents |
|---|---|---|
| **Add code** | Look up whether the symbol/file already exists (Pillar 2 step 1; new files must be registered before creation) | Duplicating something that already exists |
| **Change / refactor** | `impacted_files(path)` + `IMPORTS` edges → the dependency blast radius (Pillar 2 steps 4–5) | A rename/signature change silently breaking unseen callers |
| **Fix a defect** | `CAUSED_INCIDENT` edges → `ProductionIncident` nodes distilled from `.agent-history.log`, including how each was resolved | Re-introducing a bug that a previous session already fixed and explained |
| **Stay within context budget** | `fetch_subgraph_context_window(anchor, hops=n)` → ~200-token subgraph | Loading full files and exhausting the window (§3 "Headroom") |

Because the graph is rebuilt on every commit/checkout (and now validated in
CI via `verify_system.py --check-kg`, FIXES_AND_CLEANUP.md P10a), the recall
a new session reads is current with the committed code rather than a stale
snapshot.

---

## 11. Financial Circuit Breaker

### Budget Hierarchy

```
org cap (enterprise pack — optional)
  └── tenant cap (per tenant.id — enforced by LLM Gateway in production)
        └── workflow cap (per workflow type — defined in tenant repo)
              └── session cap (dev IDE sessions — circuit_breaker.py)
```

| Level | Backing store | Enforced by |
|---|---|---|
| Session (dev) | `.agent-rfc/fixtures/token_velocity_cache.json` | `circuit_breaker.py` |
| Tenant (production) | LLM Gateway store (Postgres or Redis) | `runtime/llm_gateway.py` |
| Org (enterprise) | `agenticframework-org.yaml` + Gateway | Enterprise pack |

### Dev Session — Dual-Tier Protection

| Tier | Threshold (default) | Scope |
|---|---|---|
| Burst velocity | 50,000 tokens / 5 minutes | Rolling window |
| Monthly cap | $150.00 USD / calendar month | Cumulative spend |

### Per-Model Pricing

Production cost accounting uses per-model rates from `models.yaml` in each tenant repo (overrides) with framework defaults. The LLM Gateway computes cost per span using the actual model id — no blended rates.

Dev session estimates use configurable approximations via env vars:
- `AGENT_COST_PER_INPUT_TOKEN` (default: $3.00/1M)
- `AGENT_COST_PER_OUTPUT_TOKEN` (default: $15.00/1M)

### Dev Session Breach Behavior (circuit_breaker.py)

On threshold breach in a dev session:
1. `circuit_breaker.py` raises `CircuitBreakerTripped`
2. Logs CRITICAL entry to `.agent-history.log`
3. Desktop notification fires
4. Background thread dispatches webhook
5. Agent halts — does not exit the worker process (production workers must survive)

### Production Breach — Degrade Ladder

Production workers route all LLM calls through the LLM Gateway. On budget breach or throttle signal:

1. **Throttle** — reduce request rate
2. **Downgrade** — route to cheaper model tier
3. **Queue** — delay tasks with exponential backoff
4. **Halt cloud inference** — switch to local Ollama if available
5. **Alert** — Ops Portal notification + Slack/Teams

Workers **never terminate** on a budget breach. Temporal activities retry with degrade semantics; Celery tasks are re-queued to DLQ on exhaustion.

---

## 12. Maintenance Schedule

| Cadence | Task | Command |
|---|---|---|
| Per commit | Log rotation (INFO/MINOR FIFO at 10,000 entries) | Automatic — post-commit hook |
| Monthly | Knowledge Graph pruning (orphan CodebaseFile nodes) | `python3 scripts/local_knowledge_graph.py --stats` then prune via API |
| As needed | Upgrade local GPU models | `ollama pull llama3 && ollama pull mistral && ollama pull gemma2` |
| On framework version bump | Upgrade vendored scripts in tenant repos | `ai-stack-upgrade --to <version>` |
| On rule changes | Sync team via installer | `./install-ai-stack.sh && source ~/.zshrc` |

---

## 13. Antigravity Integration

Antigravity is an AI coding agent that discovers and executes skills defined as markdown files in `.agents/skills/`. AgentSmith provisions Antigravity alongside other IDEs during the `post-checkout` hook.

### Skill Structure

```
.agents/skills/<skill-name>/skill.md
```

Baseline skills written on every new checkout:

| Skill directory | Purpose |
|---|---|
| `.agents/skills/efficiency_stack/` | Core lifecycle guardrails (Ponytail, Caveman, RFC compliance) |
| `.agents/skills/observability/` | OTel span emission and Phoenix integration |
| `.agents/skills/self_improvement/` | Log monitoring, repeated-failure halt, HITL escalation |

### IDE Comparison

| Feature | Cursor (`.cursorrules`) | Claude Code (`CLAUDE.md`) | Antigravity (`.agents/skills/`) |
|---|---|---|---|
| Config format | Markdown sections | Markdown with session checklist | Markdown skill files |
| Source of truth | `templates/agent-rules.yaml` | `templates/agent-rules.yaml` | `templates/agent-rules.yaml` |
| Skill composition | Single file | Single file | Multiple files, composable |

All three are generated from `templates/agent-rules.yaml` by the `post-checkout` hook. Existing files are not overwritten, preserving project-level customisations.

---

## 14. Multi-Tenant Independent Repositories

### Model

AgentSmith operates across three distinct levels:

- **Framework repo:** AgentSmith tooling — single GitHub repository, own release cycle, own semver. Tenant apps pin to a framework version.
- **Tenant repos:** One repository per customer application — independent stack, agents, promotion track, eval suite, and budget.
- **Monorepo:** Supported within one tenant (sub-package `.agent-rfc/` scoping retained).

> There is no shared customer application trunk. Tenant A production may run commit `abc` while Tenant B production runs commit `def`.

**What does not cross tenant boundaries:**
- Knowledge Graph edges
- Golden dataset cases in production gates
- Budget tracking
- HITL promotion approvals

### `.agenticframework/tenant.yaml` Schema

```yaml
tenant:
  id: acme                       # partition key used in all spans and logs
  name: Acme Corp
  isolation: shared              # shared | dedicated (dedicated = own worker pool)
framework:
  version: "1.2.0"               # pinned AgentSmith version
  mode: enterprise               # developer | enterprise
environments:
  development:
    phoenix_namespace: acme-dev
  staging:
    phoenix_namespace: acme-staging
    eval_fail_below: 0.75
  production:
    phoenix_namespace: acme-prod
    eval_fail_below: 0.80
    redaction_profile: production
```

### Machine-Level vs Per-Repo Data

| Data | Scope | Production use |
|---|---|---|
| `golden_evals_base.json` | Framework install (`~/.agent-framework/shared/`) | Bootstrap copy only; not merged in prod gate |
| `golden_evals.json` | Tenant repo (`.agent-rfc/fixtures/`) | Sole source for staging/production gates |
| `custom_judge_criteria.json` | Tenant repo | Tenant-local only |
| `machine_budget.json` | Machine / org | Dev sessions only |
| Tenant budget | LLM Gateway store | Production enforcement |
| Knowledge Graph | Tenant repo | Strictly per-repo |

### Team-Shared RFC Store (Within-Org Documentation Sharing)

`AGENT_SHARED_RFC_DIR` enables sharing RFC documentation within one organisation. It is not for cross-tenant production data linkage.

```bash
export AGENT_SHARED_RFC_DIR="$HOME/team-shared-rfcs"
```

### Monorepo Sub-Package Scoping

```
my-monorepo/
├── .agenticframework/tenant.yaml  ← tenant config for this monorepo
├── .agent-rfc/                    ← cross-cutting RFCs
├── apps/
│   ├── api/
│   │   └── .agent-rfc/            ← API-specific RFCs
│   └── web/
│       └── .agent-rfc/            ← Web-specific RFCs
└── packages/shared/
```

---

## 15. Universal Observability Platform

### Three Observability Surfaces

| Surface | Audience | Implementation |
|---|---|---|
| **Phoenix** | Developers and team leads | Arize Phoenix — traces, evals, HITL annotations |
| **Ops Portal** | Operations / cross-tenant view | `portal/` — multi-tenant pipeline view, cost, queue, unresolved issues |
| **In-App Widget** | End users of tenant applications | `templates/in-app-widget/` — read-only status component |

### Span Attributes (Mandatory)

Every OTel span must carry all of the following:

| Attribute | Source | Example |
|---|---|---|
| `tenant.id` | `.agenticframework/tenant.yaml` | `acme` |
| `tenant.name` | `.agenticframework/tenant.yaml` | `Acme Corp` |
| `project.name` | Git remote slug or directory name | `oil-price-agent` |
| `project.repo` | `git remote get-url origin` | `github.com/org/oil-price-agent` |
| `environment` | `$ENVIRONMENT` | `development`, `staging`, `production` |
| `ai_stack_mode` | `$AI_STACK_MODE` | `local`, `hybrid` |
| `agent.name` | Node function | `Architect` |
| `agent.role` | Node declaration | `orchestrator`, `subagent` |
| `agent.owner_id` | `$AGENT_OWNER_ID` | `bobby@example.com` |
| `llm.model_name` | Model factory | `claude-3-5-sonnet-20241022` |
| `input.value` | Prompt (redacted per environment) | *(see §27)* |
| `output.value` | Completion (redacted per environment) | *(see §27)* |

### Ops Portal

- **Purpose:** Cross-tenant operations view aggregating independent pipelines
- **Views:** tenant list, real run status (`agent_runs`, aggregated across concurrent/sequential calls within one workflow — "running" until every call in the group finishes), cost by tenant/agent/model with cap %, Phoenix trace count + error rate (last 24h, GraphQL), per-tenant DLQ triage with editable payload + Replay/Discard (not just an aggregate pending count), suggested shadow-eval promotion queue, audit log
- **Auth:** SSO/OIDC (enterprise pack); basic auth minimum (team deployment)
- **Data sources:** Phoenix REST/GraphQL, `agent_runs`/`dlq_entries`/`llm_gateway_budget` (Postgres), `.agent-history.log` sync

### In-App Widget

- Embeddable component in `templates/in-app-widget/`
- Displays: last agent run status, link to tenant-scoped Phoenix trace, error summary
- Read-only; tenant-scoped auth token; no cross-tenant data access

### Phoenix Deployment

| Mode | Phoenix | Auth requirement |
|---|---|---|
| Local (solo dev) | `localhost:6006` | None (local only) |
| Team-shared | `https://phoenix.team.internal` | **Required** — Caddy/nginx OAuth or basic auth |
| Production | As configured | **Required** — SSO/OIDC (enterprise pack) |

Team-shared and production Phoenix deployments **must** require authentication. An unauthenticated shared Phoenix instance is non-compliant — production traces may contain sensitive metadata even with redaction active. See `docker-compose.yml` for auth sidecar configuration.

### Project Namespacing in Phoenix

Filter by `tenant.id` or `project.name`:

```
tenant.id = "acme" AND environment = "production"
```

---

## 16. GitHub Repository

### Framework Distribution Repository

```bash
# Developer install
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash

# Pinned version (recommended for team environments)
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/download/v1.0.0/install-ai-stack.sh | bash

# With checksum verification (supply-chain safety)
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/download/v1.0.0/install-ai-stack.sh \
  -o install-ai-stack.sh
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/download/v1.0.0/install-ai-stack.sh.sha256 \
  | sha256sum --check
bash install-ai-stack.sh
```

### Repository Structure

```
AgentSmith/
├── install-ai-stack.sh          # Master installer
├── scripts/                     # Python agent scripts (dev lifecycle)
│   ├── local_knowledge_graph.py
│   ├── map_codebase.py
│   ├── local_agent_stack.py
│   ├── multi_agent_system.py
│   ├── cost_router.py
│   ├── network_watchdog.py
│   ├── notifier.py
│   ├── run-evals.py
│   ├── promote-learning.py
│   ├── sync-ui-feedback.py
│   ├── agent_logger.py
│   ├── circuit_breaker.py
│   ├── verify_system.py
│   └── generate-ide-config.py  # Reads templates/agent-rules.yaml, writes target-repo IDE config
├── runtime/                     # Production runtime components
│   ├── worker.py
│   ├── llm_gateway.py
│   ├── models.yaml              # Framework default model registry (§29)
│   ├── trace_redactor.py
│   ├── idempotency.py
│   ├── dead_letter.py
│   ├── temporal_replay.py       # Concrete Temporal replay_handler — signals a live, parked workflow
│   ├── replay_webhook_server.py # Reference receiver for the Ops Portal's "Replay with edits" action
│   ├── workflows/
│   │   └── base_workflow.py     # run_with_hitl_gate (approve/reject) + run_with_recoverable_step (edit/resume)
│   └── k8s/dedicated-tenant/    # tenant.isolation: dedicated manifests (§23, §30)
├── hooks/                       # Git hook templates (Phase 5: extracted from installer)
│   ├── pre-commit
│   ├── commit-msg
│   ├── post-commit
│   └── post-checkout
├── enterprise/                  # Enterprise pack (§30, optional)
│   ├── package-hook-bundle.sh   # Signs the org hook bundle (GPG detached sig)
│   ├── mdm-deploy-hooks.sh      # IT deployment script — verifies sig before install
│   └── agenticframework-org.yaml.example
├── templates/                   # IDE config templates
│   ├── agent-rules.yaml         # Single source of truth — read directly by
│   │                            #   scripts/generate-ide-config.py at hook-runtime;
│   │                            #   writes land in the TARGET repo (.cursorrules,
│   │                            #   CLAUDE.md, .agents/skills/), not in this directory
│   └── in-app-widget/           # Embeddable end-user status widget + Ops Portal API
├── portal/                      # Ops Portal (Next.js + TypeScript + Tailwind)
├── examples/
│   ├── oil-price-agent/         # Reference tenant app (fork per customer)
│   └── README.md                # "Copy and rename — do not deploy from framework repo"
├── fixtures/                    # Bootstrap golden dataset base
│   ├── golden_evals_base.json
│   └── custom_judge_criteria_base.json
├── docs/
│   └── team-observability.md
├── .github/
│   └── workflows/
│       ├── self-test.yml        # py_compile/shellcheck/portal/widget tests on the framework itself
│       └── release.yml          # Builds + optionally signs scripts/hooks/workflow-templates/templates tarballs
├── caddy/
│   └── Caddyfile                # Phoenix auth sidecar (§15) — used by docker-compose.auth.yml
├── requirements.txt
├── docker-compose.yml
├── docker-compose.auth.yml      # Optional overlay: HTTP basic auth in front of Phoenix (§15)
├── SPECS.md
├── Readme.md
└── UserManual.md
```

### `self-test.yml` Requirements

`verify_system.py` itself is a local-machine health check (Phoenix reachability,
Ollama/API keys, owner identity) — not meaningful in a generic CI runner with
none of that configured. The framework's own CI instead validates what's
actually checkable without live infra:
- `py_compile` sweep over `scripts/`, `runtime/`, `examples/`
- `bash -n` / `zsh -n` on `install-ai-stack.sh`, `enterprise/*.sh`, `hooks/*`
- ShellCheck (advisory, non-blocking — no existing baseline to compare against)
- Ops Portal: `tsc --noEmit` + `next build`
- In-App Widget: jsdom test suite (including the XSS-attribute-injection
  regression test — see `templates/in-app-widget/test/widget.test.mjs`)

### Framework CI/CD

The framework has its own versioned release process (see Section 28). It is not exempt from the CI guardrails it provisions for tenant repos.

---

## 17. CI/CD via GitHub Actions

### Per-Tenant Workflow Set

Each tenant repo receives four workflow files:

| Workflow | Trigger | Environment | Gate |
|---|---|---|---|
| `ci-<stack>.yml` | PR to `develop` or `main` | — | lint, test, calls `eval-scorecard.yml`; plus four Ten-Pillars gates (FIXES_AND_CLEANUP.md P10): Validate Knowledge Graph (Pillar 2, `map_codebase.py --quiet`, warn-only), RFC gate (Pillar 1, enforced only when `.agenticframework/org-policy.yaml` is present), IDE config drift (Pillar 6/7, `generate-ide-config.py --check-only`, warn-only), framework health check (Pillar 3/5, `verify_system.py`, non-blocking) |
| `eval-scorecard.yml` | `workflow_call` from `ci-<stack>.yml` (not triggered standalone) | — | eval scorecard, warn below 0.7 — shared by all three stacks (`ci-go.yml`/`ci-python-fastapi.yml`/`ci-ts-react.yml`) so a threshold/dependency change lands in one place, not three copy-pasted blocks |
| `cd-staging.yml` | Push to `develop` | staging | eval fail below 0.75 + smoke |
| `cd-production.yml` | Push to `main` | production | eval fail below 0.80 + smoke; **no `continue-on-error`** |

All workflow files include a tenant-scoped header:

```yaml
# Tenant-scoped CD — applies to THIS repository only.
# tenant.id: {{TENANT_ID}}
# Do not reference org-level shared secrets beyond this tenant's GitHub Environment.
```

### Per-Environment Secrets

| Secret | CI/PR | Staging | Production |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `staging` | `production` |
| `ANTHROPIC_API_KEY` | Required | Required | Required |
| `OPENAI_API_KEY` | Required | Required | Required |
| `AGENT_JUDGE_MODEL` | Optional | Optional | Optional |
| `AGENT_PHOENIX_ENDPOINT` | Optional | Required | Required |
| `AGENT_OWNER_ID` | `ci@...` | `ci@...` | `ci@...` |
| Deployment credentials | — | Per-platform | Per-platform |

### Container Image Build (optional)

Before the deploy step, both `cd-staging.yml` and `cd-production.yml` run
`.github/actions/build-push-ghcr`: if a `Dockerfile` exists at the tenant
repo's root, it builds and pushes `ghcr.io/<org>/<repo>:<sha>` using the
workflow's own `GITHUB_TOKEN` (no extra registry secret — just
`permissions: packages: write` on the job) and exports the pushed ref as
`$IMAGE_REF` for `DEPLOY_COMMAND` to consume. No Dockerfile → the step
skips cleanly, same "optional infra never fails CD" posture as every
other optional step in these workflows. This is also the artifact
`templates/onprem-deploy/` (§D.6/OPERATIONS.md) expects for on-premise
canary/shadow deployment.

### Rollback on Failed Production Smoke

Production smoke test failure must fail the job and invoke the platform rollback hook. This is a documented extension point:

```yaml
- name: Post-deploy smoke
  run: python3 scripts/run-evals.py --fail-below 0.80
  # No continue-on-error — failure blocks or rolls back

- name: Rollback on failure
  if: failure()
  run: |
    # Platform-specific rollback — configure for your deploy target:
    # Fly.io:   fly releases list && fly deploy --image <prev-image>
    # Railway:  railway rollback
    # AWS ECS:  aws ecs update-service --task-definition <prev-arn>
    echo "Configure rollback command for your platform"
```

Staging smoke failure blocks promotion to `main`.

### CD Golden Dataset Commits

The CD workflow opens a pull request for fixture changes — it does not push directly to `main`:

```yaml
- name: Open PR for golden dataset updates
  run: |
    git checkout -b bot/sync-evals-$(date +%s)
    git add .agent-rfc/fixtures/golden_evals.json \
            .agent-rfc/fixtures/custom_judge_criteria.json || true
    if ! git diff --cached --quiet; then
      git commit -m "feat(evals): sync HITL feedback from production"
      git push origin HEAD
      gh pr create --title "sync evals" --body "Auto-generated by CD sync"
    fi
```

`[skip ci]` is not used for eval fixture updates — CI must validate the new cases.

---

## 18. Agent Identity

### Identity Dimensions

| Dimension | Attribute key | Source | Example |
|---|---|---|---|
| **Owner** | `agent.owner_id` | `$AGENT_OWNER_ID` | `bobby@example.com` |
| **Owner display name** | `agent.owner_name` | `$AGENT_OWNER_NAME` | `Bobby Rajagopal` |
| **Tenant ID** | `tenant.id` | `.agenticframework/tenant.yaml` | `acme` |
| **Tenant name** | `tenant.name` | `.agenticframework/tenant.yaml` | `Acme Corp` |
| **Orchestrator name** | `agent.orchestrator` | Root span creator | `Supervisor` |
| **Orchestrator model** | `agent.orchestrator_model` | Model factory | `claude-3-5-sonnet-20241022` |
| **Agent name** | `agent.name` | Node function | `Architect`, `Developer`, `Validator` |
| **Agent role** | `agent.role` | Node declaration | `orchestrator`, `subagent` |
| **Agent model** | `llm.model_name` | Model factory | `llama3`, `gpt-4o` |
| **Session ID** | `agent.session_id` | UUID at workflow start | `a3f2c1...` |
| **Workflow ID** | `workflow.id` | Temporal workflow id or Celery task id | `wf-acme-oil-0042` |
| **Workflow run** | `workflow.run_id` | Engine-assigned run identifier | `run-abc123` |
| **Idempotency key** | `workflow.idempotency_key` | Activity input hash | `sha256:...` |
| **Project** | `project.name` | Git remote slug | `oil-price-agent` |
| **Repository** | `project.repo` | `git remote get-url origin` | `github.com/acme/oil-price-agent` |
| **Stack mode** | `ai_stack_mode` | `$AI_STACK_MODE` | `hybrid` |

### HITL RBAC (Enterprise Pack)

- `promoted_by` must match an allowlist (SSO group or explicit list in `tenant.yaml`)
- Enterprise pack: all promotion actions are written to an immutable audit trail
- Any Phoenix user may annotate spans — but only allowlisted users' annotations trigger automatic promotion

### Identity in `.agent-history.log`

```json
{
  "timestamp": "2026-06-22T10:34:12Z",
  "level": "MAJOR",
  "event": "empty_catch_block_detected",
  "agent": "Developer",
  "agent_role": "subagent",
  "orchestrator": "Supervisor",
  "owner_id": "bobby@example.com",
  "tenant_id": "acme",
  "session_id": "a3f2c1...",
  "project": "oil-price-agent",
  "model": "llama3",
  "hitl_resolved": false,
  "hitl_resolved_by": null,
  "hitl_resolved_at": null
}
```

---

## 19. Structured Agent History Log

### Log Levels

| Level | When used | Pruning policy |
|---|---|---|
| `INFO` | Successful commits, normal completions, mode switches | Pruned at 10,000-entry cap (FIFO) |
| `MINOR` | Non-breaking warnings, cost routing fallbacks, model substitutions | Pruned at 10,000-entry cap (FIFO) |
| `MAJOR` | Test failures, validator rejections, circuit breaker warnings | **Never pruned** until `hitl_resolved: true` |
| `CRITICAL` | Circuit breaker trips, budget cap breaches, data integrity violations | **Never pruned** until `hitl_resolved: true` |

### Rotation Policy

`INFO` and `MINOR` entries are subject to a 10,000-line rolling cap (combined). `MAJOR` and `CRITICAL` entries are never counted toward the cap.

### Ops Portal Sync

MAJOR/CRITICAL entries are synced to the Ops Portal unresolved queue in addition to the local `ai-stack-check` summary. Teams operating independent tenant repos cannot rely on each developer running `ai-stack-check` locally — centralized visibility is required.

---

## 20. IDE Config Security (`.gitignore` Confirmation)

When the `post-checkout` hook writes IDE config files into a repository, it checks the git remote URL visibility. If a public remote is detected:

```
⚠️  AgentSmith: IDE config files contain system prompt content.
    This repo appears to be public. Add them to .gitignore?
    (y/n): _
```

- If **y**: `.cursorrules`, `CLAUDE.md`, `.agents/`, `.agent-history.log` appended to `.gitignore`.
- If **n**: Files written but not gitignored. A MINOR warning logged.

Additionally, if `.agenticframework/tenant.yaml` contains non-public tenant metadata (non-default tenant id, non-public endpoint URLs), it is also included in the gitignore prompt for public repos.

In non-interactive environments (CI), the hook defaults to yes.

---

## 21. Resolved Design Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Claude Code schema | Target latest Claude Code release; use `CLAUDE.md` (current standard) |
| 2 | Arize Phoenix version | Phoenix ≥4.x API (OTLP endpoint, annotations API) |
| 3 | LangGraph version | LangGraph ≥0.2 (`StateGraph`, `interrupt`, `add_conditional_edges` v2) |
| 4 | NetworkX version | NetworkX ≥3.0; `node_link_data(G, edges="links")` format |
| 5 | Notifications | Cross-platform via `plyer`; macOS additionally uses `osascript` |
| 6 | Log levels & rotation | INFO/MINOR/MAJOR/CRITICAL; MAJOR+CRITICAL protected until HITL resolved; INFO+MINOR capped at 10,000 (FIFO) |
| 7 | IDE config in public repos | Hook prompts for confirmation; auto-adds to `.gitignore` on yes; CI defaults to yes |
| 8 | Judge model | Default `claude-3-5-sonnet-20241022`; override via `AGENT_JUDGE_MODEL` — no code change |
| 9 | Team Phoenix | Docker Compose included; auth required for team/production deployments |
| 10 | Monorepo scope | Monorepo and multi-repo fully in scope; nested `.agent-rfc/` for sub-packages |
| 11 | Agent identity | Full orchestrator + sub-agent hierarchy linked to `AGENT_OWNER_ID` |
| 12 | Runtime topology | Dual layer: dev lifecycle on workstation; production runtime in cloud |
| 13 | Tenancy | Independent repo per tenant; no shared customer trunk; no cross-tenant merges |
| 14 | Promotion | Per tenant repo: develop → staging → production; no cross-tenant promotion |
| 15 | Durable execution | Temporal (preferred) or Celery+Redis in production; `MemorySaver` dev-only |
| 16 | Observability surfaces | Phoenix (dev/team) + Ops Portal (cross-tenant ops) + In-App Widget (end users) |
| 17 | Trace redaction | Environment-dependent: full dev, scrubbed staging, minimal prod |
| 18 | Hook deployment | Developer mode: opt-in per repo; Enterprise: org-managed signed bundle, bypass disabled |
| 19 | LLM routing | `cost_router.py` dev-only; LLM Gateway mandatory in production |
| 20 | Golden evals | Tenant-local for gates; framework base is bootstrap-only, not merged in prod |
| 21 | Enterprise pack | Optional: SSO, audit trail, dedicated tenant isolation, compliance notes |

---

## 22. Deliverables Checklist

### Phase 0 — Spec Alignment (current)
- [x] Apply all changes from architecture review to SPECS.md (this document)
- [x] Fix `.claudecode.json` → `CLAUDE.md` across all docs and scripts
- [x] Standardize knowledge graph path to `.agent-rfc/fixtures/knowledge_graph.json`
- [x] Fix hybrid data-locality wording in §8 and scripts
- [x] Fix `ai-stack-on` → `ai-mode-local` in installation steps
- [x] Refresh §21 with decisions 12–21
- [x] Phase §22 deliverables

### Phase 1 — Tenant Scaffold
- [x] `.agenticframework/tenant.yaml` schema and `ai-tenant-init` command
- [x] Per-tenant CI/CD workflow templates (ci + cd-staging + cd-production)
- [x] `tenant.id` wired into all OTel spans and log entries in `agent_logger.py`

### Phase 2 — Production Runtime
- [x] `runtime/` package stubs (worker, gateway, redactor, idempotency, DLQ)
- [x] Temporal reference workflow in `examples/oil-price-agent/`
- [x] Full implementation of `runtime/llm_gateway.py`
- [x] Full implementation of `runtime/trace_redactor.py`
- [x] Postgres checkpointer; `MemorySaver` marked dev-only in docs

### Phase 3 — Observability
- [x] `portal/` stub directory
- [x] `templates/in-app-widget/` stub
- [x] Ops Portal v1 implementation
- [x] In-App Widget implementation
- [x] Phoenix auth sidecar in `docker-compose.yml`

### Phase 4 — Enterprise Pack (optional)
- [x] Org hook bundle signing and MDM deploy script
- [~] SSO for portal and Phoenix — Ops Portal OIDC done (`portal/lib/oidc.ts`); Phoenix is still basic-auth-only via the Caddy sidecar (§15) — true Phoenix OIDC needs a custom Caddy build with an auth plugin (e.g. `caddy-security`), not yet built/tested
- [x] Immutable audit log schema
- [x] Dedicated worker pool per tenant (`isolation: dedicated`)

### Phase 5 — Framework Hygiene
- [x] Extract hooks to `hooks/` directory (from heredocs in `install-ai-stack.sh`)
- [x] `.github/workflows/self-test.yml` and `release.yml` for framework itself
- [x] `templates/agent-rules.yaml` single-source IDE config generation
- [x] `generate-ide-config.py --check-only` IDE config drift gate + `verify_system.py --check-kg` Knowledge Graph gate wired into tenant CI and `self-test.yml` (FIXES_AND_CLEANUP.md P10)
- [x] `ai-stack-uninstall` command implementation
- [x] `ai-stack-upgrade` command implementation

### Already Delivered (from v0.3.0)
- [x] `SPECS.md` formal specification
- [x] `Readme.md` (formal, with happy-flow example)
- [x] `UserManual.md` (17 sections)
- [x] `install-ai-stack.sh` (9-section idempotent installer)
- [x] `requirements.txt` (pinned ranges)
- [x] All 14 Python scripts in `scripts/`
- [x] IDE config single source (`templates/agent-rules.yaml` + `scripts/generate-ide-config.py`)
- [x] GitHub Actions workflow templates (`workflow-templates/`)
- [x] `docker-compose.yml` (Phoenix + PostgreSQL)
- [x] `docs/team-observability.md`

---

## 23. Tenancy Model (Independent Repositories)

### Definition

A **tenant** is a customer application with its own independent repository, agents, eval suite, deployment track, and runtime budget. The framework serves multiple tenants from one install; tenants do not share production infrastructure, data, or code.

### Framework Repo vs Tenant Repo

| Responsibility | Framework repo | Tenant repo |
|---|---|---|
| IDE guardrail rules | Provides templates | Uses generated files |
| Eval baseline | Provides bootstrap JSON | Owns and grows the dataset |
| Python scripts | Provides and versions | Vendors (Option A) or fetches at CI (Option B) |
| Workflows | Provides templates | Defines own Temporal/Celery workflows |
| Agents | Provides reference patterns | Implements domain agents |
| Release cadence | Own semver | Pins framework version; upgrades independently |

### Tenant Isolation Tiers

| Tier | `isolation` value | Worker pool | Budget scope | Phoenix namespace |
|---|---|---|---|---|
| Shared (default) | `shared` | Partitioned by `tenant.id` | Per-tenant within shared pool | Filtered by `tenant.id` attribute |
| Dedicated | `dedicated` | Own pool, own infra | Isolated | Own Phoenix project |

`isolation` is validated against this exact two-value enum wherever it's
accepted — `ai-tenant-init --isolation`, and `POST /api/tenants` in the Ops
Portal (`isolation` is also a DB-level `CHECK` constraint on the `tenants`
table). An unrecognized value (a typo like `dedicated-typo`) is rejected at
write time rather than stored verbatim and silently treated as `shared` by
whichever code path branches on `isolation === "dedicated"`.

### Explicit Non-Goals

- No cross-tenant merges
- No shared production deployment
- No cross-tenant golden dataset merging in production gates
- No shared `.agent-history.log` across tenants
- No cross-tenant Knowledge Graph edges

---

## 24. Per-Tenant Lifecycle and Promotion

### Branch → Environment Mapping (per tenant repo)

| Branch | Environment | Workflow |
|---|---|---|
| Feature/PR | development | `ci-<stack>.yml` — lint, test, evals (warn gate) |
| `develop` | staging | `cd-staging.yml` — eval fail gate + smoke |
| `main` | production | `cd-production.yml` — eval fail gate + smoke + rollback hook |

### `ai-tenant-promote` Semantics

Promotion is always within the same tenant repo:

```bash
ai-tenant-promote acme --from staging --to production
# 1. Verifies staging eval gate passed
# 2. Opens PR from develop → main in the tenant repo
# 3. Requires review approval before merge
# 4. After merge: cd-production.yml fires
```

Cross-tenant promotion does not exist. The guard that enforces this does an
**exact match** against the `tenant.id` field parsed from
`.agenticframework/tenant.yaml` — a substring match (e.g. `acme` matching a
`tenant.yaml` with `id: acme-sandbox`) would let `ai-tenant-promote acme ...`
run against a similarly-named but different tenant's repo by mistake.

### GitHub Environments per Repo

Each tenant repo configures two GitHub Environments (`staging`, `production`) with:
- Required reviewers (for production)
- Environment-scoped secrets (deployment credentials, API keys)
- Deployment protection rules (eval gate must pass before deploy step runs)

### Fixture Promotion via PR

Golden dataset and judge criteria changes go through pull request review in the tenant repo. Direct push to `main` is blocked by branch protection. CI validates the new cases before the PR can be merged.

### Framework Version Pin and Upgrade

```bash
# Check current version
ai-stack-status

# Upgrade vendored scripts in current tenant repo
ai-stack-upgrade --to 1.2.0

# Applies: copies new script versions to scripts/, commits as:
# "chore(framework): upgrade AgentSmith to v1.2.0"
```

---

## 25. Production Runtime

### Workflow Engine Selection

| Engine | Status | When to use |
|---|---|---|
| **Temporal** | Recommended | Complex multi-step workflows, HITL pauses, cross-service coordination |
| **Celery + Redis** | Supported fallback | Simpler task chains, existing Celery infrastructure |
| LangGraph `MemorySaver` | **Dev only — prohibited in production** | IDE sessions, rapid prototyping |

### Worker Topology

```
runtime/worker.py entrypoint
    │
    ├─ Reads tenant.id from task context
    ├─ All LLM calls → runtime/llm_gateway.py (not cost_router.py)
    ├─ All spans carry tenant.id, workflow.id, workflow.run_id
    └─ All failures → dead_letter.py (DLQ)
```

Shared pool: all tenants run on the same worker fleet, partitioned by `tenant.id` in task routing.

Dedicated pool: tenant gets own worker deployment. Configured via `tenant.isolation: dedicated`. Provisioned separately per tenant.

### Idempotency Key Design

Every workflow activity is assigned an idempotency key derived from a hash of its input parameters. Duplicate activity submissions (e.g., on retry after crash) are detected and short-circuited. `runtime/idempotency.py` manages the key store (Redis or Postgres-backed).

Unlike the budget backend (§29, which has an in-memory option for dev/CI), idempotency has **no in-memory fallback** — only `_RedisBackend` and `_PostgresBackend` (`IDEMPOTENCY_BACKEND` env var, default `redis`). If `REDIS_URL`/`DATABASE_URL` isn't set or the backend can't connect, `LLMGateway._make_idempotency_store()` (`runtime/llm_gateway.py:355-367`) catches the failure, logs a warning, and degrades to no idempotency store at all — the gateway still runs, but duplicate-call suppression silently doesn't happen until a real backend is reachable.

### Dead-Letter Queue

Failed activities — including ones a human can *fix and replay*, not just
ones that exhaust retries — are moved to the DLQ (`runtime/dead_letter.py`).
Operations:

```python
dlq.enqueue(payload, error, tenant_id, task_id=None,
            reason=None, workflow_id=None, gate_id=None)
dlq.list(tenant_id=None, limit=100, status="pending")
dlq.replay(task_id, override_payload=None)  # re-submits via replay_handler; override_payload
                                              # is the human-edited fix (e.g. correcting a
                                              # hallucinated field name before resuming)
dlq.discard(task_id)  # removes from DLQ + marks resolved
```

`enqueue()` is idempotent on `task_id` (`ON CONFLICT DO NOTHING`) and posts
to `SLACK_WEBHOOK_URL`/`TEAMS_WEBHOOK_URL` if configured. `reason` is a
structured category (`validation_error`, `tool_call_error`,
`hitl_timeout`, `hitl_rejected`, `infra_error`) so the Ops Portal can
render "needs a human decision" differently from "needs an engineer."
`workflow_id`/`gate_id` are present only for entries created by
`run_with_recoverable_step` (below) — they identify the *live, still-
parked* workflow a replay should resume, as opposed to a terminated
dead-letter with nothing left to resume.

`replay()`'s constructor-supplied `replay_handler` is workflow-engine-
specific and pluggable; `runtime/temporal_replay.py`'s
`make_temporal_replay_handler(client)` is the concrete Temporal
implementation — it signals the workflow at `entry.workflow_id` with
`human_fix_payload(gate_id, fix)`.

DLQ entries surface in the Ops Portal's per-tenant triage view
(`/dlq/<tenantId>`) — editable payload, Replay, Discard — not just an
aggregate pending count.

### HITL Pause / Resume

Two related patterns in `runtime/workflows/base_workflow.py`, for two
different kinds of human intervention:

**Approve/reject** (`run_with_hitl_gate`) — workflow waits on a boolean
signal:

```python
await workflow.wait_condition(lambda: self._hitl_approved is not None, timeout=timedelta(hours=24))
# On timeout: DLQ entry created (reason="hitl_timeout"), workflow terminates ("dead_letter" status)
```

**Edit-and-resume** (`run_with_recoverable_step`) — for failures the
human fixes rather than approves/rejects (e.g. an agent's tool call
hallucinates `{"account_status": "active"}` where the schema expects
`"status"`). On activity failure, the workflow stays **alive** — it does
not terminate — enqueues a DLQ entry carrying its own `workflow_id`/
`gate_id`, and waits on the `human_fix_payload` signal up to a caller-
configurable timeout (bounded by `max_attempts`, default 5, so a human
submitting fixes that keep failing doesn't park the workflow forever):

```python
await self.run_with_recoverable_step(
    "crm_update_activity", payload, tenant_id=tenant_id, gate_id="crm-update-gate",
    timeout=timedelta(hours=24),
)
# On human_fix_payload signal: retries the SAME activity with the corrected payload,
# resuming in place — not a fresh execution.
```

**Important:** the gated `execute_activity` call uses
`retry_policy=RetryPolicy(maximum_attempts=1)` — Temporal's *default*
policy retries the same failing payload indefinitely (with backoff) until
`start_to_close_timeout`, which wastes up to that whole timeout before the
recoverable-step logic even engages, for a payload that won't succeed on
retry without being different. The method's own attempt loop is the
intended retry mechanism, not Temporal's.

**The portal has no Temporal client and never gains one** — when a human
edits a payload in the Ops Portal's DLQ view and clicks Replay, the
portal HMAC-signs the edit and POSTs it to **that tenant's own**
`replay_webhook_url`/`replay_webhook_secret` (synced from
`.agenticframework/tenant.yaml`'s `hitl.replay_webhook_url`/
`hitl.replay_webhook_secret`, same mechanism as `gateway.budget_cap_usd`)
— deliberately per-tenant, so a fix is always routed to the team running
that tenant's worker, never a shared cross-tenant endpoint.
`runtime/replay_webhook_server.py` is the reference receiver: verifies
the signature, then calls
`DeadLetterQueue(replay_handler=make_temporal_replay_handler(client)).replay(task_id, override_payload=...)`.

In Celery: task chains pause at a HITL checkpoint task; resume via `task.apply_async()` on approval. The edit-and-resume pattern's Celery equivalent is tenant-implemented — `run_with_recoverable_step` is Temporal-specific (workflow signals); a Celery worker would re-queue the checkpoint task with the corrected payload instead.

### Scheduling

Per-tenant cron is defined in tenant repo config, not in the framework. The framework provides a reference:

```yaml
# .agenticframework/schedules.yaml (tenant repo)
schedules:
  - name: daily-prediction
    workflow: oil_price_prediction
    cron: "0 6 * * *"
    timezone: UTC
```

### Domain Workflow Ownership

Reference workflows in `runtime/workflows/` demonstrate patterns only. Tenant repos define their own production workflow files. Framework workflows are never deployed directly as tenant production code.

### On-Premise / Air-Gapped Deployment

`templates/onprem-deploy/` — opt-in via `ai-onprem-deploy-scaffold`, never
auto-written the way the CI/CD workflow templates are (not every tenant
has an on-prem customer). Stack-agnostic by design, consistent with the
framework's own position as something that builds "other" applications
of any architecture: it assumes only that a tenant app ships as **one
container image**, listens on **one HTTP port** answering `GET /healthz`,
reads config from **env vars only** (no cloud secret manager call), and
logs **JSON-Lines to stdout**.

| Target | When | Mechanism |
|---|---|---|
| Docker Compose | ~80% of on-prem customers — single server/VM | `docker compose up -d`, canary + shadow routing via Traefik or Envoy (customer's choice) |
| Kubernetes / Helm | High-compliance enterprise, won't run raw Docker | `helm install`, canary via the **core** Gateway API's `backendRefs[].weight` (portable across Traefik's and Envoy Gateway's controllers); shadow via the core `RequestMirror` filter (always-100%, no percentage field in the standard spec — Compose's native Traefik/Envoy mirroring does support a percent if that's needed) |

Canary/shadow proxy config is rendered from `.env` by
`scripts/render-{traefik,envoy}-config.py` (a real dict + `yaml.safe_dump`,
not string templating) — both validated against actual `docker compose
config` and (for Helm) `helm lint`/`helm template`, not just written and
assumed correct.

Shadow traffic *mirroring* here is infrastructure-level (tests a new app
version against live request shape before promotion) — distinct from
`scripts/shadow-eval.py`'s *application-level* shadow evaluation (§9),
which judges a sample of already-served production traces after the
fact, safely, since it never re-executes anything. Don't point a
mirror-shadow container at a build that isn't side-effect-safe in dry-run
mode — the proxy replays the HTTP request verbatim with no knowledge of
what the app does with it.

Air-gapped bundling: `scripts/bundle-airgapped.sh`/`load-airgapped.sh`
(`docker save`/`docker load`, zero registry calls on the target host).
See `templates/onprem-deploy/README.md` and
`templates/onprem-deploy/kubernetes/README.md` for the full walkthrough;
OPERATIONS.md §D.6 for the operator-facing quickstart.

---

## 26. Federated Observability

### Three Surfaces and Their Audiences

| Surface | Primary audience | Access | Data scope |
|---|---|---|---|
| **Phoenix** | Developer, tech lead | Developer local or team server | One tenant's traces + evals |
| **Ops Portal** | Operations team, platform team | Web app with SSO | All tenants (filtered by `tenant.id`) |
| **In-App Widget** | End user of tenant application | Embedded in tenant UI, read-only | Own session only |

### Phoenix Namespacing

Every span carries `tenant.id`. Filtering in Phoenix:

```
tenant.id = "acme" AND environment = "production"
```

Cross-tenant aggregation is available in the Ops Portal only — not in per-developer Phoenix instances.

### Ops Portal Data Model

The Ops Portal aggregates data from:
1. Phoenix API — traces, experiments, annotations
2. Workflow engine metrics — queue depth, active workflows, DLQ depth
3. LLM Gateway — per-tenant spend, per-model cost breakdown
4. `.agent-history.log` sync — unresolved MAJOR/CRITICAL entries per tenant

Ops Portal API contract is defined in `portal/README.md`.

### In-App Widget Integration

Tenant applications embed the widget via:

```html
<!-- From templates/in-app-widget/ -->
<!-- Self-hosted: download widget.js from a tagged release and serve it yourself -->
<script src="/static/widget.js"></script>
<agent-status tenant-id="acme" token="<read-only-token>"></agent-status>
```

The widget reads from Phoenix (via a read-only scoped API token). It displays no data from other tenants.

### Cross-Tenant Aggregation Without Data Leakage

The Ops Portal aggregates metrics by `tenant.id` attribute. Raw span content (prompts, completions) is never displayed cross-tenant — only aggregated counts, costs, and status flags. Role-based access in the portal (viewer, operator, admin) controls which tenants each user can view.

### Role-Based Access Control

Every authenticated request resolves to an `Access { role, tenantScope }`
(`portal/lib/authz.ts`) before any tenant data is read:

| Role | Can view | Can write (`POST /api/tenants`, mint widget tokens) | Can revoke widget tokens | Can view audit log |
|---|---|---|---|---|
| `viewer` | Tenants in `tenantScope` only | No | No | No |
| `operator` | Tenants in `tenantScope` only | Yes | No | No |
| `admin` | Tenants in `tenantScope` only (or all, if `tenantScope: "*"`) | Yes | Yes | Yes |

Mint and revoke are deliberately split: minting a widget token is routine
tenant-onboarding work (same tier as creating the tenant itself), revoking
one instantly breaks every live embed for that tenant — a more disruptive
action reserved for `admin`.

`tenantScope` is either `"*"` (all tenants) or an explicit allow-list of
tenant ids. This is enforced server-side in every route under
`portal/app/api/tenants/**`, `portal/app/page.tsx`, and
`portal/app/tenants/[id]/page.tsx` — never client-side only.

**Basic auth (`OPS_PORTAL_USERS`):** a JSON array of
`{ username, password, role, tenants }`. The legacy single-user
`OPS_PORTAL_USER`/`OPS_PORTAL_PASSWORD` pair remains supported for backward
compatibility and is granted `admin`/`"*"` automatically; `OPS_PORTAL_USERS`
takes precedence when set.

**SSO (`OPS_PORTAL_SSO_USERS`):** a JSON array of
`{ email, role, tenants }`, keyed by the IdP's email claim
(case-insensitive). An authenticated SSO identity that does not appear in
this list gets the most restrictive possible access — `viewer` with an
**empty** tenant scope — rather than being rejected outright or defaulting
to full access.

`middleware.ts` resolves access once per request and forwards it downstream
to route handlers and pages as trusted `x-af-role` / `x-af-tenant-scope`
request headers, stripping any client-supplied copy of those same header
names first so a caller cannot simply set `x-af-role: admin` itself.

A dedicated test suite (`portal/test/authz.test.ts`, run via `npm test` in
`portal/`) asserts cross-tenant isolation directly: a viewer scoped to one
tenant cannot read another's cost/issues data, an unlisted SSO identity gets
zero tenants (not all), and forged role/scope headers do not grant access.

---

## 27. Trace Redaction

### Redaction Profiles

| Profile | `environment` value | `input.value` / `output.value` | PII / secrets |
|---|---|---|---|
| `none` | `development` | Full (up to 1,000 chars) | Unrestricted |
| `staging` | `staging` | Patterns stripped; structure preserved | Hashed identifiers |
| `production` | `production` | Hashed or truncated to 50 chars | Full payload in encrypted HITL blob only |

### `trace_redactor.py` Integration

`runtime/trace_redactor.py` acts as an OTLP processor — it intercepts spans before export and applies the active redaction profile:

```python
# profile/tenant_id are optional overrides; normally resolved automatically —
# profile via runtime/environment.py:get_environment(), tenant_id per-span
# (see "Per-Span Tenant Binding" below).
redactor = TraceRedactor()
provider.add_span_processor(redactor)
```

### Canonical Environment Resolution

`runtime/environment.py:get_environment()` is the single source of truth for
`$ENVIRONMENT`, shared by `trace_redactor.py` (redaction profile) and
`scripts/multi_agent_system.py` (checkpointer selection). It is
**fail-closed**: an unset or unrecognized value (e.g. a typo) resolves to
`"production"` — the strictest redaction profile and the path that requires
a Postgres checkpointer — never to `"development"`. A production worker pod
that loses its `ENVIRONMENT` env var therefore gets the safe failure mode
(maximum redaction, hard error without `DATABASE_URL`) in both places
consistently, instead of silently falling back to unredacted span export in
one code path while erroring loudly in the other for the same
misconfiguration.

### Per-Span Tenant Binding

`TraceRedactor` resolves the tenant id for HITL blob encryption from the
span's own `tenant.id` attribute (set by `runtime/llm_gateway.py` and the
agent scripts) inside `on_end()`, not from a value captured once at
`__init__`/process-construction time. On a shared (non-dedicated) worker
pool processing spans for multiple tenants in one process, binding
tenant_id per-process instead of per-span would encrypt every HITL-flagged
span with whichever tenant's `HITL_ENCRYPTION_KEY` the processor happened to
be constructed with — a cross-tenant data leak. The constructor-supplied
`tenant_id` (or `$TENANT_ID`) is only a fallback for spans that carry no
`tenant.id` attribute at all.

### Encrypted HITL Blob

When a production span is flagged for HITL review, the full payload is encrypted and stored separately:
- Encryption: AES-256-GCM with per-tenant key
- Storage: S3 or equivalent object store
- TTL: 90 days (configurable per tenant)
- Access: HITL reviewer only, via Ops Portal — not accessible from Phoenix UI
- Blob reference key: `{trace_id}.{span_id}.{attr_key}` — `span_id` is
  required, not optional: without it, multiple independently HITL-flagged
  sibling spans in the same trace (e.g. Architect/Developer/Validator) would
  compute the same ref and the last write would silently overwrite the
  earlier spans' encrypted payloads before anyone reviewed them.
- A missing/unconfigured `HITL_ENCRYPTION_KEY` for a tenant is logged at
  ERROR (not silently swallowed) — the span is still truncated/scrubbed as
  designed, but the dropped blob is now visible instead of leaving a
  `hitl_blob_ref` that points at nothing.

### Secret/PII Pattern Library

Default patterns detected and redacted:
- API keys: `sk-...`, `sk-ant-...`, bearer tokens
- Email addresses
- Credit card numbers (Luhn-valid patterns)
- IP addresses (optional — disabled by default in staging)

Tenant repos extend the pattern library via `.agenticframework/redaction-patterns.yaml`.

### CI Validation

The `cd-staging.yml` and `cd-production.yml` workflows include a redaction compliance step:

```bash
python3 scripts/verify_system.py --check-redaction
# Fails if staging/production profile emits raw API key patterns in test fixture spans
```

---

## 28. Framework vs Application Release

### AgentSmith Semver

- `vMAJOR.MINOR.PATCH` — breaking changes (hook API, span contract) increment MAJOR
- Releases are tagged via the framework's own `post-commit` hook
- Signed release artifacts published via `release.yml`
- Release notes document any span attribute changes or hook interface changes

### Tenant Pinning

Tenants pin the framework version in `.agenticframework/tenant.yaml`:

```yaml
framework:
  version: "1.2.0"
```

The `ai-stack-upgrade` command upgrades vendored scripts to the pinned version. Tenants upgrade on their own schedule — there is no forced upgrade.

### Compatibility Matrix

The framework maintains a compatibility matrix in `CHANGELOG.md`:

| Framework version | Min Python | Min LangGraph | Min Phoenix | Breaking changes |
|---|---|---|---|---|
| 1.0.x | 3.11 | 0.2 | 4.0 | Initial release |
| 1.1.x | 3.11 | 0.2 | 4.0 | None |
| 1.2.x | 3.11 | 0.2 | 4.1 | Span attribute `project.name` renamed from `service.name` for project-level spans |

### Examples as Forks

`examples/oil-price-agent/` is a reference tenant application. It demonstrates the full stack but is **never deployed directly from the framework repo**. The README in `examples/` states:

> Copy and rename this directory into your own repository. Do not deploy from AgentSmith/examples. This is a reference implementation, not a production deployment target.

---

## 29. LLM Gateway (Production)

### Purpose

Centralised production LLM routing, distinct from the dev-mode `cost_router.py` heuristics. The gateway provides:
- Accurate per-model pricing (not blended estimates)
- Per-tenant budget enforcement
- Degrade ladder on budget/quota breach
- Audit trail of all production LLM calls
- Mandatory for all production agent LLM calls

### Gateway API

`runtime/llm_gateway.py` exposes:

```python
gateway.complete(
    prompt=messages,
    model_hint="developer",      # architect | developer | validator | fast
    tenant_id="acme",
    workflow_id="wf-oil-0042",
    idempotency_key="sha256:...",
    max_tokens=4096,
)
# Returns: CompletionResult(text, model_used, input_tokens, output_tokens, cost_usd)
```

### Model Registry (`models.yaml`)

Per tenant repo (overrides) with framework defaults:

```yaml
# models.yaml
models:
  architect:
    id: claude-sonnet-4-6
    provider: anthropic
    cost_per_input_token: 0.000003
    cost_per_output_token: 0.000015
  developer:
    id: gpt-4o
    provider: openai
    cost_per_input_token: 0.0000025
    cost_per_output_token: 0.00001
  groq_fast:
    id: llama-3.3-70b-versatile
    provider: groq             # OpenAI-compatible; defaults to GROQ_API_KEY
    cost_per_input_token: 0.00000059
    cost_per_output_token: 0.00000079
  fast:
    id: gemma2
    provider: ollama
    endpoint: "${OLLAMA_BASE_URL}/v1"
    cost_per_input_token: 0
    cost_per_output_token: 0
```

### Per-Tenant Routing Overrides

Tenants can override model selection per agent role without touching framework code:

```yaml
# .agenticframework/tenant.yaml
gateway:
  routing_overrides:
    developer: llama3-70b-8192   # cheaper model for this tenant
    validator: claude-3-haiku    # fast validation
```

### Degrade Ladder

On budget breach or provider throttle:

1. **Throttle** — exponential backoff on request rate
2. **Downgrade** — route to next cheaper tier in `models.yaml`
3. **Queue** — enqueue with delay up to `max_queue_delay`
4. **Local fallback** — switch to Ollama if available
5. **Halt + alert** — Ops Portal + Slack/Teams

Workers never terminate on a gateway error. All gateway decisions are recorded as span attributes: `llm.gateway.tier`, `llm.gateway.degrade_reason`.

### Atomic Budget Reservation

Budget enforcement is reserve-then-reconcile, not check-then-act:
`LLMGateway.complete()` atomically reserves an upper-bound cost estimate
(`max_tokens × (cost_per_input_token + cost_per_output_token)`) against the
budget backend **before** invoking the provider, via
`_BudgetBackend.try_reserve(tenant_id, amount, cap)` — an indivisible
check-and-add per backend (an atomic Postgres `UPDATE ... WHERE spent_usd +
$1 <= cap`, a Redis `INCRBYFLOAT` with compensating rollback on overshoot,
or a lock-guarded add for the in-memory backend). After the call returns,
the reservation is reconciled to the actual cost via a signed delta
(`add_spend` accepts negative amounts). A separate read-then-write — read
current spend, then write only after the LLM call returns — would let N
concurrent calls for the same tenant all observe "not breached" before any
of them recorded spend, letting the combined cost of every in-flight call
exceed the monthly cap.

### Budget Backend Selection

`BUDGET_BACKEND` (env var: `memory` | `postgres` | `redis`, default `memory`)
chooses the `_BudgetBackend` implementation `_make_budget_backend()`
instantiates:

| | Dev (`memory`) | Prod (`postgres`) | Prod (`redis`) |
|---|---|---|---|
| Process scope | Single process only | Cross-process / cross-worker | Cross-process / cross-worker |
| Config | None required | `DATABASE_URL` | `REDIS_URL` |
| Durability | In-memory dict, lost on restart | WAL-backed, durable | In-memory unless persistence is configured |
| `try_reserve` mechanism | `threading.Lock`-guarded add | Atomic `UPDATE ... WHERE spent_usd + $1 <= cap` | `INCRBYFLOAT` + compensating rollback on overshoot |
| Queryable alongside other data | No | Yes — joinable with `agent_runs`/`dlq_entries` | No — key-value only |
| Existing infra needed | None | Already provisioned if the Ops Portal is deployed (shares `DATABASE_URL`) | Separate service unless Redis is already used elsewhere (e.g. idempotency cache, rate limiting) |
| When to pick | Local dev, unit tests, CI — no external services available or desired | Multi-worker prod fleets, especially when Postgres is already running for the portal and durability/auditability of spend matters | Multi-worker prod fleets needing the lowest-latency reserve path under high concurrency, or consolidating onto Redis already used for other purposes |

The single-process `memory` backend is unsafe for multi-worker prod fleets
specifically because of the race `try_reserve` exists to close (see
"Atomic Budget Reservation" above) — that race only manifests across
*multiple* processes sharing one tenant's budget cap, which is the normal
prod topology but not the typical dev/CI one.

### Mandatory Gateway Enforcement

All production workers import `runtime/llm_gateway.py` and **must not** import `cost_router.py` directly. The framework's `pre-commit` hook (enterprise mode — an org policy file present at `~/.agent-framework/agenticframework-org.yaml`) greps staged `runtime/*.py` files for direct `cost_router` imports and blocks the commit if found.

### Shared Provider Dispatch

`runtime/llm_gateway.py` and the dev-mode `scripts/cost_router.py` share
request-building and response-parsing logic via
`runtime/provider_dispatch.py` (`build_request`, `parse_response`,
`infer_provider`) — only the provider-dispatch shape (Anthropic Messages API
vs. OpenAI-compatible chat completions) is shared; each file's own
routing/budget/degrade-ladder logic, which legitimately differs between the
dev-mode and production paths, stays local to each file.

### Cloud-Native Provider Adapters

Direct-API providers (`anthropic`, `openai`/`openai_compatible`) share one
host and static API-key auth, handled by `build_request`/`parse_response`
above. Cloud-hosted models don't — each cloud vendor has its own auth scheme
and request/response envelope, not just a different host. `models.yaml`
entries with `provider: vertex_ai | azure_openai | bedrock |
huawei_modelarts` are dispatched instead to a `CloudProviderAdapter`
(`runtime/provider_dispatch.py`):

| Provider | Auth | URL shape | Required `models.yaml` fields | Default region | Live-verified? |
|---|---|---|---|---|---|
| `vertex_ai` (GCP) | OAuth2 service-account token (`google-auth`) | `{region}-aiplatform.googleapis.com/.../publishers/{publisher}/models/{id}:streamRawPredict\|generateContent` | `project` (supports `${VAR}` expansion); optional `region`, `publisher` (defaults to `google`/Gemini) | `us-central1` | **Yes** — `gemini-2.5-flash` round-tripped end-to-end through `LLMGateway.complete()` against a real GCP project |
| `azure_openai` | `api-key` header + `api-version` query param | `{resource}.openai.azure.com/openai/deployments/{deployment}/chat/completions` | `resource`; optional `deployment`, `api_version`, `api_key_env` | n/a | No — mocked only |
| `bedrock` (AWS) | SigV4-signed request (`boto3`/`botocore`, standard credential chain) | `bedrock-runtime.{region}.amazonaws.com/model/{id}/invoke` | optional `region` | `us-east-1` | No — mocked only |
| `huawei_modelarts` | AK/SK request signing (`SDK-HMAC-SHA256`, `HUAWEICLOUD_SDK_AK`/`_SK` env vars) | per-deployment custom inference endpoint host | `endpoint` | n/a (required field, no default) | No — mocked only, least-documented of the four |

Each adapter implements the same `build_request(model_id, messages, cfg,
max_tokens, temperature) -> (full_url, headers, body)` /
`parse_response(data) -> (text, input_tokens, output_tokens)` shape (a
`CloudProviderAdapter` protocol) — unlike the direct-API path, cloud
adapters return a full URL rather than a path, since project/region/
deployment/endpoint-id are baked into the URL itself, not split out as a
separate base_url. All four support an optional `url_template` (or, for
Huawei, `path_template`) override falling back to the defaults above.

**GCC region note (live-verified for GCP, not for AWS):** an earlier
default pointed Vertex AI and Bedrock at GCC regions (`me-central1`/
`me-central2` for GCP, `me-central-1` for AWS) on an untested assumption
that GCC-locality was generally desirable. A live test against a real
Vertex AI project found `gemini-2.5-flash` returns 404 in both GCP GCC
regions (works in `us-central1`/`europe-west1`/`europe-west4`/
`asia-south1`) — both defaults were reverted to the verified-working
regions above. The GCC regions remain valid `region:` overrides for either
provider, just no longer the default; verify model availability live
before relying on one, especially for Bedrock (no AWS credentials were
available to test its GCC region the way Vertex AI's was).

`runtime/models.yaml` has a live-verified `vertex_gemini` role
(`gemini-2.5-flash` / `us-central1`) as an opt-in entry — not wired into
the architect/developer/validator degrade chain, since most tenants won't
have GCP credentials configured. Route to it via
`model_hint="vertex_gemini"` or a tenant's `routing_overrides`.

All four adapters are covered by mocked request/response-shape tests
(`runtime/test/test_provider_dispatch_cloud.py`); `vertex_ai` additionally
has the live verification described above. The Huawei ModelArts adapter
in particular is the least-documented in English-language sources; its
signing implementation follows Huawei's published algorithm structure but
should be verified against a real deployment before production use.

### Budget Period Timezone

Both the LLM Gateway's Postgres/Redis budget period key and the Ops
Portal's "current month" lookup (`portal/lib/cost.ts`) are pinned to UTC
explicitly (`runtime/llm_gateway.py:_current_period()` uses `time.gmtime()`,
not the server's local time) — a worker running in a non-UTC timezone would
otherwise disagree with the portal for several hours around a month
boundary about which period a charge belongs to.

---

## 30. Enterprise Install and Compliance Pack

### Overview

The enterprise pack is an optional layer providing governance controls for organisations running AgentSmith across multiple teams or meeting compliance requirements. It does not change the core framework behaviour — it adds enforcement, auditability, and isolation controls.

### Org Hook Bundle

Enterprise install produces a signed hook bundle:

```
agenticframework-hooks-<version>.tar.gz      # hook files
agenticframework-hooks-<version>.tar.gz.sig  # detached GPG signature
agenticframework-org.yaml                    # org policy file
mdm-deploy-hooks.sh                          # IT deployment script template
```

Policy file schema:

```yaml
# agenticframework-org.yaml
hooks:
  version: "1.2.0"
  bypass_policy: disabled           # disabled | break-glass
  break_glass_approvers: ["it-sec@example.com"]
phoenix:
  endpoint: "https://phoenix.corp.internal"
  auth: oidc
sso:
  provider: okta
  issuer: "https://corp.okta.com"
  client_id: "..."
```

### Bypass Policy

| Policy | Developer action | IT action |
|---|---|---|
| `disabled` (default enterprise) | No bypass available | IT provides break-glass token |
| `break-glass` | Can request emergency bypass | Approves via IT portal; event written to audit log |

**Break-glass token format:** `AI_BREAK_GLASS_TOKEN` is not merely checked
for presence — it must be a real, IT-issued token in the form
`<actor>:<expires_epoch>.<hex_hmac_sha256>`, validated locally
(`_ai_validate_break_glass_token` in `install-ai-stack.sh`) by recomputing
the HMAC-SHA256 signature over `<actor>:<expires_epoch>` with
`BREAK_GLASS_HMAC_KEY` (a secret IT controls and distributes out-of-band —
distinct from the per-use token itself) and checking the embedded expiry.
A non-empty string that isn't a validly-signed, unexpired token is
rejected and logged as a denied `hook_bypass` event, same as no token at
all. A machine where `BREAK_GLASS_HMAC_KEY` isn't configured cannot
validate any break-glass token and refuses the bypass outright.

All bypass events are written to the immutable audit log — best-effort to
the Ops Portal (`OPS_PORTAL_URL` + `AUDIT_LOG_WRITE_TOKEN`), with a local
fallback (see "Audit Log Local Fallback" below) when that write doesn't
happen, so a break-glass bypass is never silently unrecorded anywhere.

### Immutable Audit Log Schema

| Field | Type | Description |
|---|---|---|
| `event_id` | UUID | Unique event identifier |
| `timestamp` | ISO-8601 | UTC timestamp |
| `event_type` | enum | `hook_bypass`, `hitl_promotion`, `config_change`, `tenant_created` |
| `actor_id` | string | SSO user ID |
| `tenant_id` | string | Affected tenant |
| `details` | object | Event-specific data |
| `signature` | string | HMAC-SHA256 of event fields |
| `tenant_id` foreign key | — | References `tenants(tenant_id)` with no `ON DELETE` cascade/null action — a tenant with audit history simply cannot be deleted, by design: a `SET NULL` would itself be an `UPDATE` on this table and get rejected by its own append-only trigger, and `CASCADE` would let a tenant teardown silently erase its own bypass/config-change history. |

### Audit Log Local Fallback

`_ai_audit_log_event` (in `install-ai-stack.sh`) never blocks the calling
command on the Ops Portal's availability — but it also no longer drops
events silently. If `OPS_PORTAL_URL`/`AUDIT_LOG_WRITE_TOKEN` are unset, or
the write to `POST /api/audit/append` fails (portal down, network error,
non-2xx response), the event is appended as a JSON line to
`~/.agent-framework/local-audit-fallback.log` instead, tagged with the
reason (`ops_portal_not_configured` or `ops_portal_write_failed`). This is
a local trace for later reconciliation, not a substitute for the Ops
Portal's immutable, signed audit log — it has no signature, no tamper
protection, and no cross-machine visibility.

### SSO Integration

When enterprise pack is enabled:
- Ops Portal requires SSO login (OIDC)
- Phoenix is placed behind SSO proxy
- GitHub SAML enforced for tenant repos
- `promoted_by` in HITL records is the SSO user identity (not just email)
- Each SSO identity's role and tenant scope are resolved via
  `OPS_PORTAL_SSO_USERS` (see §26 "Role-Based Access Control") — SSO
  authentication alone does not imply any particular tenant access
- The session JWT carries a `jti` claim and supports server-side
  revocation: `POST /api/auth/logout` records the session's `jti` in the
  `revoked_sessions` table (not the token itself), and every authenticated
  request checks it via `GET /api/auth/session-status` before trusting an
  otherwise-valid, unexpired session cookie. This check fails open (treats
  an unreachable revocation store as "not revoked") rather than locking out
  every SSO user on a transient DB hiccup — the 8h session TTL already
  bounds how long a missed revocation can matter.

### Dedicated Worker Pool

When `tenant.isolation: dedicated`:
- Tenant gets its own worker deployment (separate Kubernetes namespace or VM set)
- Budget is enforced at the infrastructure level (separate LLM Gateway instance)
- Traces stored in a separate Phoenix project with no cross-tenant query access

### Compliance Notes (SOC2-Oriented)

These are documentation notes for compliance mapping. They are not a guarantee of certification.

| Control area | AgentSmith mechanism |
|---|---|
| Access control | SSO/OIDC for portal + Phoenix; HITL RBAC allowlists |
| Audit trail | Immutable audit log for promotions, config changes, bypasses |
| Data isolation | Tenant partitioning in workers, Phoenix, LLM Gateway |
| Encryption at rest | Encrypted HITL blobs (AES-256-GCM); Postgres encryption at rest |
| Change management | Branch protection + eval gate on every merge; fixture PRs required |
| Monitoring | Ops Portal; unresolved MAJOR/CRITICAL surfaced; shadow evals |
