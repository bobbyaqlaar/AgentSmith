<p align="center">
  <img src="assets/Logo_AgentSmith.png" alt="AgentSmith Logo" width="200">
</p>

# AgentSmith

**One install. Every agent. Every project.**

AgentSmith is a single-command setup that provisions the complete AI agent
lifecycle environment on your machine or team server. Install it once and
every project you opt in gets guardrails, observability, evaluation,
self-improvement, and CI/CD — automatically.

> **Scope:** this document introduces AgentSmith — objectives, architecture,
> features, differentiators, and license. It contains no procedures beyond
> the Quick Start: installation/configuration/operations live in
> [OPERATIONS.md](./OPERATIONS.md), the formal specification in
> [SPECS.md](./SPECS.md), day-to-day dev usage in
> [UserManual.md](./UserManual.md).

---

## Objectives

1. **Design before code** — no agent writes a line until a written spec
   (RFC) exists; architecture decisions are recorded, not re-litigated.
2. **Observe everything** — every token, tool call, cost, and latency
   metric streams to a dashboard, attributed to a real human owner.
3. **Gate quality continuously** — a growing golden dataset and LLM judge
   score every pull request and every production deploy.
4. **Keep humans in the loop** — high-impact actions pause for approval;
   failures a human can fix are edited and resumed in place, never lost.
5. **Control cost** — budgets are enforced per session, per tenant, and per
   month, with atomic reservation and a graceful degrade ladder.
6. **Learn from production** — real failures become eval cases and judge
   rules that gate every future change.
7. **Ensure security by design** — controls map to **OWASP LLM Top 10**,
   **NIST AI RMF**, **MITRE ATLAS**, and **ISO/IEC 42001** themes via a
   unified `SEC-*` harness: prompt injection guard, tool allowlist,
   structured-output gate, PII scrub, moderation hook, tamper-evident
   audit, and strict CI evidence packs.
8. **Stay compliant to evolving regulations** — UAE **PDPL** decision-path
   PII handling, **Federal Decree-Law No. 34/2023** fairness gates,
   sovereign / in-border model profiles, and mandatory HITL for high-impact
   actions — built into the rails, not bolted on after launch.
9. **Stay reliable** — three-tier recovery (Temporal retries → opt-in
   self-correction → human DLQ), hallucination-rate hard gates, and
   streaming TTFT budgets so failures are recovered, not lost.
10. **Scale with the workload** — shared or dedicated Temporal worker pools,
    multi-tenant isolation, on-prem canary/shadow routing, and a degrade
    ladder that keeps serving when providers or budgets tighten.
11. **Enforce fairness** — paired fairness suites with pair-parity scoring,
    CI-gateable thresholds, and domain overlays for protected attributes.

---

## What It Sets Up

| Layer | What you get |
|---|---|
| **IDE Guardrails** | `.cursorrules`, `CLAUDE.md`, `.agents/skills/` — generated for Cursor, Claude Code, and Antigravity from one template on every checkout |
| **Git Hooks** | Pre-commit safety checks, commit message linting, automatic semantic versioning, AST codebase mapping |
| **OpenTelemetry & Observability** | OTel span contract → Arize Phoenix — one instance per machine or team, per-project and per-tenant namespacing, owner/cost/token attribution |
| **Ops Portal** | Cross-tenant ops dashboard — run history, cost vs cap, DLQ triage, HMAC append-only audit log, RBAC / optional SSO |
| **Workflow Orchestration** | Durable agents via **Temporal** (primary) or **Celery** — HITL pause/resume, recoverable steps, shared or dedicated worker pools |
| **LLM Gateway** | Single choke point for provider calls — budget reservation, degrade ladder, circuit breaker, redaction, prompt guard, moderation hook |
| **Vector / RAG Memory** | Short-term conversation memory + vector store substrate (`embeddings.py` / `vector_store.py`; hash or sentence-transformers; optional pgvector) |
| **Security Framework** | `run-security-checks.py` + `SEC-*` registry — OWASP LLM · NIST AI RMF · MITRE ATLAS · ISO/IEC 42001 evidence packs in CI (`strict: true`) |
| **Regulations Compliance** | UAE / sovereign starter (`templates/uae-sovereign/`), PDPL pre-call scrub, fairness + adversarial eval suites, ISO thematic control map |
| **Evaluations** | Golden dataset + LLM-as-judge scorecard gating every PR; fairness, hallucination, adversarial, and TTFT suites |
| **Multi-Agent Orchestration** | Architect → Developer → Validator pipeline — local Ollama or cloud frontier models |
| **Knowledge Graph** | AST-driven codebase graph, auto-updated on every commit and checkout — zero context drift |
| **Self-Improvement** | Human-in-the-Loop promotion loop: production failures become test cases become guardrail rules |
| **Cost & Budget Guard** | Dual-tier circuit breaker — burst velocity limit + monthly spend cap with cross-platform notifications |
| **CI/CD** | GitHub Actions workflows for TypeScript/React, Python/FastAPI, and Go — written automatically per project (incl. security harness) |
| **Agent Identity** | Every span, log entry, and trace tied to an orchestrator, sub-agents, and a real human owner |

---

## Architecture

Two layers, joined by one OpenTelemetry span contract
(SPECS.md §3 has the full diagrams and the end-to-end integration flow):

- **Layer 1 — Dev Lifecycle (workstation):** IDE guardrails, git hooks,
  local/hybrid LLM routing, PR evaluations, Knowledge Graph,
  self-improvement loop. Installed once per developer machine.
- **Layer 2 — Production Runtime (cloud):** durable workflow orchestration
  (Temporal/Celery), tenant-scoped deployment, LLM gateway with per-tenant
  budget enforcement, environment-aware trace redaction, Ops Portal.

### Functional layers

Summary only — the canonical, reasoned mapping (including what is
deliberately *not* built and why) is **SPECS.md §4a**.

| Layer | Status | Implementation |
|---|---|---|
| Reasoning & Planning | Reference patterns | Architect→Developer→Validator graphs (`multi_agent_system.py` / `local_agent_stack.py`) — a shape to copy, not a generic planner |
| Tool Orchestration | Execution + recovery | Temporal activities + recoverable steps; `@tool` schema-extraction and MCP stay tenant-owned (settled decision) |
| Memory Management | Shipped v1 | Short-term `conversation_memory.py`; structured long-term Knowledge Graph; vector RAG substrate (`vector_store.py` + `embeddings.py`) |
| Perception & Input Parsing | Shipped v1 | `structured_output.parse_llm_json` (Pydantic); reference pipelines may still use ad-hoc JSON until migrated |
| Human-in-the-Loop | Most built-out | Approve/reject gate, edit-and-resume DLQ, opt-in LLM self-correction |

### Non-functional layers

| Layer | Status | Implementation |
|---|---|---|
| Observability & Traceability | Full | Per-span tenant/owner/cost/token attribution via OTel → Phoenix; opt-in TTFT on streaming |
| Reliability & Accuracy | Shipped v1 | Correctness/tool-accuracy/latency/hallucination judged per case; three-tier auto-retry (Temporal → self-correction → human DLQ) |
| Security & Guardrails | Shipped | Pre-call PII + prompt guard; tool allowlist; moderation hook; post-call redaction; encrypted HITL blobs; security harness CI |
| Explainability | Infrastructure-level | HMAC-signed append-only audit log + full trace history — every action auditable |
| Scalability & Performance | Shipped | Shared/dedicated Temporal worker pools; on-prem canary/shadow routing; TTFT budget gate |
| Data Bias & Fairness | Shipped v1 | Paired fairness suite + pair parity, CI-gateable |
| Continuous Improvement | Shipped | HITL promotion loop + passive shadow-eval sampler (never auto-promotes) |

---

## Quick Start

```bash
# 1. Install (once per machine)
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash
source ~/.zshrc

# 2. Identity + mode + dashboard
export AGENT_OWNER_ID="you@example.com" AGENT_OWNER_NAME="Your Name"
ai-mode-local          # or ai-mode-hybrid (cloud APIs)
ai-dashboard-start     # → http://localhost:6006

# 3. Apply to a project
mkdir my-project && cd my-project && git init -b main
# → hooks fire, IDE rules + CI workflows written, Knowledge Graph seeded
```

Full setup (env vars, `.env` files, GitHub secrets, prerequisites):
**OPERATIONS.md §0–1**. Daily commands: **UserManual.md §17**.

### Opt-in model

Hooks install machine-wide, but only *provision and enforce* in repos that
opted in: a brand-new `git init` opts in automatically; a pre-existing or
cloned repo is left untouched until you opt it in explicitly
(`mkdir -p .agenticframework && touch .agenticframework/enabled`, then any
checkout). Cloning an unrelated open-source project never gets AgentSmith
files written into it.

---

## The Ten Pillars

The operational guardrails AgentSmith enforces on every project it touches
(full specification: SPECS.md §4):

1. **Requirements & Design** — no code without a spec in `.agent-rfc/`.
2. **Build Architecture (Ponytail)** — native libraries over custom
   abstractions; 5-step analysis before any new file.
3. **Tracing & Evaluations** — every token and tool call streamed to
   Phoenix via OpenTelemetry.
4. **Testing Guardrails** — paired tests for every change, enforced in CI;
   regression tests are never cleared to force green.
5. **Operations & Self-Improvement** — structured event log
   (`.agent-history.log`); MAJOR/CRITICAL entries protected until a human
   resolves them.
6. **Interface Constraints (Caveman)** — agents output code and data only;
   no pleasantries or meta-commentary.
7. **Stack-Specific Rules** — TS/React, Python/FastAPI, and Go rules
   injected into all three IDEs on checkout.
8. **Observability Wire** — the OTel endpoint embedded in IDE configs so
   agent requests stream to the dashboard without extra setup.
9. **Multi-Agent Orchestration** — stateful Architect → Developer →
   Validator pipeline with HITL pause; offline (Ollama) or cloud with
   automatic network fallback.
10. **Cost-Optimisation Routing** — each task routed to the cheapest capable
    model; dual-tier circuit breaker prevents budget bleed.

---

## Supported Stacks & Execution Modes

| Stack | Detected by | CI workflow |
|---|---|---|
| TypeScript / React | `package.json` | `ci-ts-react.yml` |
| Python / FastAPI | `requirements.txt` / `pyproject.toml` | `ci-python-fastapi.yml` |
| Go | `go.mod` | `ci-go.yml` |
| Generic | *(fallback)* | *(hooks only, no CI workflow)* |

**Local offline** — everything on your machine via Ollama
(falcon3/llama3/mistral/gemma2), zero API cost. **Hybrid cloud** — frontier
models (Claude Sonnet 4.6 / GPT-4o) for complex tasks, open-source via
Groq/Ollama for the rest, automatic local fallback when the network drops.
Switch instantly: `ai-mode-local` / `ai-mode-hybrid`.

In hybrid mode, prompts and completions go to cloud provider APIs; trace
data always stays at your configured Phoenix endpoint (SPECS.md §8).

---

## Beyond Solo Dev: Multi-Tenant, Production, Enterprise

Built and tested against real infrastructure (Postgres, Redis, Temporal,
Kubernetes, a live OIDC provider). Operator procedures: OPERATIONS.md.

| Layer | What it adds |
|---|---|
| **Multi-Tenancy** | `ai-tenant-init` / `ai-tenant-promote` — independent tenant repos with their own CI/CD, eval gates, and staging → production promotion |
| **Production Runtime** | `runtime/` — LLM gateway (atomic per-tenant budgets, degrade ladder), trace redaction, idempotency + DLQ, Temporal HITL workflows incl. edit-and-resume and opt-in self-correction; cloud adapters (Vertex AI live-verified; Azure OpenAI / Bedrock / Huawei ModelArts mock-tested) |
| **Ops Portal** | Cross-tenant cost/issues dashboard, RBAC, per-tenant DLQ triage with replay, HMAC-signed tamper-evident audit log, SSO/OIDC with server-side revocation |
| **On-Premise** | `templates/onprem-deploy/` — Docker Compose or Helm for air-gapped customers, canary + shadow routing (Traefik or Envoy) |
| **In-App Widget** | `templates/in-app-widget/` — embeddable end-user status component, token-scoped, self-hosted |
| **Enterprise Pack** | GPG-signed hook bundles + MDM deploy, HMAC-validated break-glass bypass, RFC-enforcement hooks, dedicated per-tenant worker pools |

---

## Differentiator: UAE / Sovereign Compliance

UAE deployments need more than a global SaaS chatbot: **in-border
inference**, **bias accountability**, **HITL stop-gates**, **PDPL-aligned
PII handling**, and governance embedded in the architecture (aligned toward
ISO/IEC 42001). AgentSmith maps each mandate to shipped controls:

| Mandate (illustrative) | AgentSmith control (shipped) |
|---|---|
| Sovereign / in-border models | `templates/uae-sovereign/` — Falcon 3 on Ollama (live-verified) or a sovereign OpenAI-compatible API; smoke `scripts/verify_sovereign_endpoint.py` |
| Bias / Federal Decree-Law No. 34/2023 | `run-evals.py --suite fairness` + pair parity; CI via `eval-fairness.yml` |
| HITL for high-impact actions | `run_with_hitl_gate`, `run_with_recoverable_step`, opt-in `run_with_self_correction` → DLQ |
| PDPL / PII in the decision path | Pre-call `runtime/input_guardrail.py` (Emirates ID, etc.) + post-call `trace_redactor.py` |
| Oversight / ISO/IEC 42001 themes | `docs/iso-42001-control-map.md` + HMAC audit log + eval gates (hallucination, fairness, TTFT) |
| Multi-framework security (OWASP · NIST · ATLAS · ISO) | `docs/security-framework-map.md` — `SEC-*` controls + `run-security-checks.py` (P12 shipped) |
| Delivery governance | `docs/delivery-model.md` + `verify_system.py --check-delivery-model` |

Canonical map: **[docs/uae-regulatory.md](./docs/uae-regulatory.md)**
(not legal advice / not certification).
Starter pack: **[templates/uae-sovereign/](./templates/uae-sovereign/)**.

---

## Documentation

| Document | Owns |
|---|---|
| [SPECS.md](./SPECS.md) | Formal specification: architecture, functional→technical mapping, schemas, contracts, decision log, repository structure |
| [OPERATIONS.md](./OPERATIONS.md) | Full operator lifecycle: install → create/configure repos → test → deploy (GitHub CI/CD) → monitor → HITL/DLQ → improve → maintain → shut down |
| [UserManual.md](./UserManual.md) | Day-to-day solo/dev-mode usage + the canonical command reference |
| [CHANGELOG.md](./CHANGELOG.md) | Release notes + compatibility matrix |
| [Product_Archive.md](./Product_Archive.md) | Build history (read-only) |
| [FIXES_AND_CLEANUP.md](./FIXES_AND_CLEANUP.md) | Remaining to-do items |
| [docs/](./docs/) | Topic canon: security framework map, UAE regulatory, ISO 42001 map, delivery model, RAG/memory, team observability |

---

## License and Trademark

Released under the
[GNU Affero General Public License v3.0 (AGPL-3.0)](./LICENSE).

The name **AgentSmith**, the AgentSmith logo, and associated marks are
subject to trademark protections — the software license grants no rights to
them. Commercial use of the marks requires written permission. See
[TRADEMARK.md](./TRADEMARK.md).
