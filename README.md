<p align="center">
  <img src="assets/Logo_AgentSmith.png" alt="AgentSmith Logo" width="200">
</p>

# AgentSmith

**The governance layer across the lifecycle of an app or agent — from design to operate.**

AgentSmith makes development with AI coding agents secure, reliable and
explainable, and carries the same rules into production:

- **Design and build.** No code before a written design that answers every
  pillar. While an AI coding agent works, AgentSmith holds its IDE to that
  design; review passes and CI gates check the same rules before anything
  merges. Every decision, deviation and approval is recorded in git, so why the
  code is the way it is can always be answered.
- **Operate.** The running app gets the same rules as guardrails — budgets,
  prompt and tool controls, PII handling, human-in-the-loop for high-impact
  actions — and is observable: traces, cost, run status and incidents for every
  app, in one portal.

AgentSmith is not a CI/CD system or a monitoring stack. It runs on the ones you
have — GitHub Actions, OpenTelemetry, Phoenix — and git stays the record of
every change. Install it once per machine, and every app you opt in is governed
from its first commit.

A governed repository points at a **provider**, not at AgentSmith's files, so the coupling is to a
published contract rather than to a file layout — see *How a repository is governed* below.

**Where the portal stands.** One portal with three areas. **Dev** shows, for
every app, how each change was designed, reviewed and gated — sent by the app's
CI. **Ops** shows tracing (Phoenix, OpenTelemetry), spend, run status, incident
history, dead-letter replay and a tamper-evident audit log. **Administration**
registers apps and issues their CI tokens. Next: passkey sign-in and approving
deviations in the portal, then the HITL queue, production approvals and log
monitoring.

> **What this is:** an introduction to AgentSmith — what it is for, how it is built, and what
> sets it apart. The Quick Start below is the only procedure here; the rest is in the documents
> listed at the end.

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
| **IDE Guardrails** | `.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.agents/skills/` — generated for Cursor, Claude Code, Codex, Gemini CLI, Copilot and Antigravity from one template on every checkout |
| **Git Hooks** | Pre-commit safety checks, commit message linting, automatic semantic versioning, AST codebase mapping |
| **OpenTelemetry & Observability** | OTel span contract → Arize Phoenix — one instance per machine or team, per-project and per-tenant namespacing, owner/cost/token attribution |
| **Portal** | One portal, three areas — **Dev** (each app's commits as its gate judged them: designs, deviations, reviews, repairs), **Ops** (run history, cost vs cap, DLQ triage, HMAC append-only audit log) and **Administration** (apps and their CI tokens); seven roles granted per app, optional SSO |
| **Workflow Orchestration** | Durable agents via **Temporal** (primary) or **Celery** — HITL pause/resume, recoverable steps, shared or dedicated worker pools |
| **LLM Gateway** | Single choke point for **workload** provider calls — budget reservation, degrade ladder, circuit breaker, redaction, prompt guard, moderation hook. Workers and activities must not bypass it. The eval harness (`scripts/cost_router.py`) is the one path that does not go through it, by design — see docs/UserManual.md |
| **Vector / RAG Memory** | Short-term conversation memory + vector store substrate (`embeddings.py` / `vector_store.py`; hash or sentence-transformers; optional pgvector) |
| **Security Framework** | `run-security-checks.py` + `SEC-*` registry — OWASP LLM · NIST AI RMF · MITRE ATLAS · ISO/IEC 42001 evidence packs in CI (`strict: true`) |
| **Regulations Compliance** | UAE / sovereign starter (`templates/uae-sovereign/`), PDPL pre-call scrub, fairness + adversarial eval suites, ISO thematic control map |
| **Evaluations** | Golden dataset + LLM-as-judge scorecard gating every PR; fairness, hallucination, adversarial, RAG-poisoning, and TTFT suites |
| **Multi-Agent Orchestration** | Architect → Developer → Validator pipeline — local Ollama or cloud frontier models |
| **Knowledge Graph** | AST-driven codebase graph, auto-updated on every commit and checkout — zero context drift |
| **Self-Improvement** | Human-in-the-Loop promotion loop: production failures become test cases become guardrail rules |
| **Cost & Budget Guard** | Dual-tier circuit breaker — burst velocity limit + monthly spend cap with cross-platform notifications |
| **CI/CD** | GitHub Actions workflows for TypeScript/React, Python/FastAPI, and Go — written automatically per project (incl. security harness) |
| **Agent Identity** | Every span, log entry, and trace tied to an orchestrator, sub-agents, and a real human owner |

---

## Architecture

Two layers, joined by one OpenTelemetry span contract — and reached by a tenant through the gate
contract above (docs/DESIGN.md › System Architecture has the full diagrams and the end-to-end
integration flow):

- **Layer 1 — Dev Lifecycle (workstation):** IDE guardrails, git hooks,
  local/hybrid LLM routing, PR evaluations, Knowledge Graph,
  self-improvement loop. Installed once per developer machine.
- **Layer 2 — Production Runtime (cloud):** durable workflow orchestration
  (Temporal/Celery), tenant-scoped deployment, LLM gateway with per-tenant
  budget enforcement, environment-aware trace redaction, Ops Portal.

### Functional layers

Summary only — the canonical, reasoned mapping (including what is
deliberately *not* built and why) is **docs/DESIGN.md › Architecture by Layer**.

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

## How a repository is governed

AgentSmith is the reference implementation of a **contract**, not a set of files you copy.

A governed repository holds one declaration — `.agenticframework/providers.json`, written by
`agentsmith tenant adopt`:

```json
{
  "_about": "Who governs this repository. The hooks ask this before they ask the framework's own paths…",
  "contract": 1,
  "providers": {
    "gate": { "command": "agentsmith gate", "version": "^2" }
  }
}
```

The git hooks ask *that* — not AgentSmith's paths. At the three events the contract covers
(`session-start`, `pre-edit`, `stop`) the resolved provider receives a JSON `GateEvent` on stdin and
answers with a `Decision` on stdout: allow, deny, block, or extra context. `"gate": "none"` declares
a repository deliberately ungoverned, and is never overridden by a fallback.

**CI is in the contract** since gate contract 2: a tenant's gates workflow runs its provider's
pinned setup step and asks the declared command whether the pushed range passes, never a framework
path. **The local commit and push are in it too** since gate contract 3: a tenant's git hooks ask
the declared command, and hold no policy of their own. A third-party provider can now govern a
repository end to end — editing, commits, pushes and CI — and the knowledge graph a review is scoped
by is the repository's own data in a published shape.

Two things follow:

- **Another platform can govern your repository.** The contract is published under
  [`contract/gate/v3/`](contract/gate/v3/) (versions 1 and 2 stay published) with schemas, golden
  cases and a conformance suite. `agentsmith conformance --provider "<your command>" --contract 3` scores
  any implementation against the same cases AgentSmith's own adapter is scored against — so "or another provider" is checkable
  rather than claimed.
- **A major AgentSmith release costs you one merged pull request.** Everything a tenant still holds
  — the gate hooks, the IDE hook wiring, the rules block, the workflows — is framework-owned and
  recorded with its hash. `agentsmith sync` refreshes exactly those, leaves anything you edited
  alone and says so, and a weekly workflow opens the pull request for you. The commit it writes is
  accepted by your own gates *by hash*, not by asking you to review framework code you did not
  write.

**Where the ports stand.** Five things a tenant needs from a governance platform; the gate and the
rules are resolved through their contracts today, the records are published, and the rest are
contracts in place that still resolve to AgentSmith:

| Port | What it provides | Status |
|---|---|---|
| **Gate** | a decision at `session-start`, `pre-edit`, `stop`, on each commit and push, and on a CI range; the review scope from the knowledge graph | **declared and resolved** via `contract/gate/v3` — editing, commit, push and CI |
| **Telemetry** | spans, metrics, resource attributes | already vendor-neutral — OTLP and the span contract in CHANGELOG.md |
| **Rules** | what the agent is told | **declared and resolved** via `contract/rules/v1` — `render` and `check`; the tenant's CI checks its rule files against the provider it declares |
| **Records** | what CI decided, per commit | **published** — `contract/record/v1`: the record and its transport, with conformance for a sender and for a receiver; the portal and AgentSmith's provider are both held to it |
| **Security and evals** | artifact schemas and a harness verdict | a contract in place — the `SEC-*` registry and evidence packs |

---

## Quick Start

```bash
# 1. Install (once per machine) — latest published release
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/latest/download/install-ai-stack.sh | bash
# → the `agentsmith` command at ~/.local/bin; nothing is added to your shell profile
# From a checkout instead (no release download): ./install-ai-stack.sh

# 2. Mode + dashboard  (identity needs no export: it resolves from
#    tenant.yaml `tenant.owner`, else `git config user.email`; the mode is
#    recorded for every process on the machine, IDEs and hooks included)
agentsmith mode local          # or agentsmith mode hybrid (cloud APIs)
agentsmith dashboard start     # → http://localhost:6006

# 3. Bring a repository under the gates — the usual case, an existing one
cd my-existing-repo
agentsmith tenant adopt my-app          # prints a plan; --yes to write it
# → .agenticframework/providers.json, armed gate hooks (your own hooks still run),
#   IDE hook wiring, a rules block appended to your CLAUDE.md, two workflows.
#   Nothing of AgentSmith's code is copied into your tree.
git commit …                            # adopt prints the exact command

# 4. Stay current — or let the weekly workflow open the pull request
agentsmith sync                         # plan; --yes to write
```

Full setup (env vars, `.env` files, GitHub secrets, prerequisites):
**docs/UserManual.md › Install & Start, Create an AgentSmith-Governed Repo**. Daily commands: **docs/UserManual.md › Command Reference**.

### The other transport: a vendored repository

A repository can instead hold AgentSmith's own `scripts/` and `runtime/` in its tree. This is how
onboarding worked first, it is deliberately still supported, and it is what `agentsmith tenant init`
plus the machine hooks give you:

```bash
mkdir my-project && cd my-project && git init -b main
git commit --allow-empty -m "chore: init"   # git runs no post-checkout on init
mkdir -p .agenticframework && touch .agenticframework/enabled
git checkout                                # → IDE rules, CI workflows, vendored code, Knowledge Graph
```

Prefer `tenant adopt` unless you specifically want the framework's code in your repository: a
vendored tree is a copy, and a copy is the thing that drifts. `agentsmith sync` refreshes both.

### Opt-in model

Hooks install machine-wide, but only *provision and enforce* in repos that
opted in: a brand-new `git init` opts in automatically; a pre-existing or
cloned repo is left untouched until you opt it in explicitly — by
`agentsmith tenant adopt`, or by `touch .agenticframework/enabled` and a
checkout. Cloning an unrelated open-source project never gets AgentSmith
files written into it.

---

## The Sixteen Pillars

The operational guardrails AgentSmith enforces on every project it touches
(full specification: docs/DESIGN.md › Operational Pillars). **Fourteen of the sixteen are answered
in every design** — P5 and P6 are standing rules a review pass works down instead:

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
6. **Interface Constraints (Caveman)** — agents skip pleasantries and filler
   summaries, but always state what failed, what risk they took and what they
   assumed. Terse, not silent.
7. **Stack-Specific Rules** — TS/React, Python/FastAPI, and Go rules
   injected into every agent config on checkout.
8. **Observability Wire** — the OTel endpoint embedded in IDE configs so
   agent requests stream to the dashboard without extra setup.
9. **Multi-Agent Orchestration** — stateful Architect → Developer →
   Validator pipeline with HITL pause; offline (Ollama) or cloud with
   automatic network fallback.
10. **Cost-Optimisation Routing** — each task routed to the cheapest capable
    model; dual-tier circuit breaker prevents budget bleed.
11. **Untrusted Content** — retrieved documents, tool output and error strings
    are data, never instructions. Poisoned chunks are quarantined individually,
    because failing a whole retrieval on one bad document is a denial of service.
12. **Secrets and Credentials** — never in source, logs or commit messages; the
    credential's variable *name* is read from the registry, not hardcoded.
13. **Gate Integrity** — a check passes by being satisfied, never by being
    weakened. Where a control cannot be proven, the claim is split and the
    remainder declared a gap.
14. **Fixture and Baseline Drift** — re-pin baselines in the same change, after
    checking which projection of the output each fixture holds.
15. **Ambiguous Signals** — one value must not mean two things. "Measured zero" and
    "never measured" are different facts, and a check that could not run says so
    rather than reporting a pass.
16. **Recovery Paths** — every fallback has its own failure. Where does control go
    then, and what state does the next rung receive?

---

## Supported Stacks & Execution Modes

| Stack | Detected by | CI workflow | CI installs from |
|---|---|---|---|
| TypeScript / React | `package.json` | `ci-ts-react.yml` | `package-lock.json` (npm) or `pnpm-lock.yaml` (pnpm) — yarn, bun or no lockfile fails CI by name |
| Python / FastAPI | `requirements.txt` / `pyproject.toml` | `ci-python-fastapi.yml` | `requirements.txt`, else `uv.lock` (must match `pyproject.toml`) — anything else installs only CI tooling, with a warning |
| Go | `go.mod` | `ci-go.yml` | `go.mod` |
| Generic | *(fallback)* | *(hooks only, no CI workflow)* | — |

**Local offline** — everything on your machine via Ollama, zero API cost; the
shipped registry routes four roles (`architect` → `developer` → `validator` →
`fast`) to local models, and `agentsmith models --ollama` prints the exact ids.
**Hybrid cloud** — the same roles pointed at frontier providers for complex
tasks, with automatic local fallback when the network drops. Cloud routes ship
commented out in `models.yaml`; uncomment one or declare your own to enable
them. Switch modes: `agentsmith mode local` / `agentsmith mode hybrid`.

In hybrid mode, prompts and completions go to cloud provider APIs; trace
data always stays at your configured Phoenix endpoint (docs/DESIGN.md › Multi-Agent Execution Modes).

---

## Beyond Solo Dev: Multi-Tenant, Production, Enterprise

Built and tested against real infrastructure (Postgres, Redis, Temporal,
Kubernetes, a live OIDC provider). Operator procedures: docs/UserManual.md.

| Layer | What it adds |
|---|---|
| **Multi-Tenancy** | `agentsmith tenant init` / `agentsmith tenant promote` — independent tenant repos with their own CI/CD, eval gates, and staging → production promotion |
| **Production Runtime** | `runtime/` — LLM gateway (atomic per-tenant budgets, degrade ladder), trace redaction, idempotency + DLQ, Temporal HITL workflows incl. edit-and-resume and opt-in self-correction; cloud adapters (Vertex AI live-verified; Azure OpenAI / Bedrock / Huawei ModelArts mock-tested) |
| **Portal** | Dev workspace fed by each app's CI gate, cross-app cost/issues dashboard, per-app DLQ triage with replay, HMAC-signed tamper-evident audit log, seven per-app roles, SSO/OIDC with server-side revocation |
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

One document per kind, each for a different question:

| Document | Answers |
|---|---|
| [docs/UserManual.md](docs/UserManual.md) | How do I install, use and operate it? The command reference is its last section of Part I |
| [docs/DESIGN.md](docs/DESIGN.md) | How is it built, and why this way? |
| [docs/PRODUCT_BACKLOG.md](docs/PRODUCT_BACKLOG.md) | What is still open? |
| [docs/PRODUCT_ARCHIVE.md](docs/PRODUCT_ARCHIVE.md) | How did it get this way — what was decided, when, and what it replaced? |
| [docs/REVIEW_LOG.md](docs/REVIEW_LOG.md) | What did each review find, and what closed it? |
| [CHANGELOG.md](CHANGELOG.md) | What changed in each release, and what is compatible with what? |
| [contract/gate/v3/protocol.md](contract/gate/v3/protocol.md) | What must a governance provider do to satisfy the gate contract? |

Reference material a tenant reads — the security framework map, the UAE regulatory notes, the
ISO 42001 map, the delivery model, RAG and memory, team observability — is under
[docs/](docs/).

---

## License and Trademark

Released under the
[GNU Affero General Public License v3.0 (AGPL-3.0)](./LICENSE).

The name **AgentSmith**, the AgentSmith logo, and associated marks are
subject to trademark protections — the software license grants no rights to
them. Commercial use of the marks requires written permission. See
[TRADEMARK.md](./TRADEMARK.md).
