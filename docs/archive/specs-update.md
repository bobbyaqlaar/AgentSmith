# SPECS.md Update Requirements

> **Archived (2026-06-22):** Planning doc from the architecture review. Substantive changes were merged into [SPECS.md](../../SPECS.md). Kept for history only.

**Target document:** [SPECS.md](../../SPECS.md)  
**Based on:** Architecture review (2026-06-22) with confirmed design decisions  
**Status:** ~~Proposed~~ **Merged into SPECS.md v0.4+**

---

## Confirmed Design Decisions

These decisions drive every change below. SPECS.md should state them explicitly in §1 and §21.

| # | Topic | Decision |
|---|-------|----------|
| 1 | Runtime target | **Dual layer:** dev on workstation; production in cloud |
| 2 | Observability | **Three surfaces:** Phoenix (traces/evals/HITL) + ops portal (cross-tenant ops) + in-app widget (end-user status) |
| 3 | Promotion model | **Independent per tenant (B):** each customer project is a separate repo with its own `develop` → staging → production track; no shared customer `main` across tenants |
| 4 | Team scale | **Small team default;** enterprise compliance (SSO, audit, isolation) as optional pack |
| 5 | Long-running agents | **Job queue required:** Temporal (preferred) or Celery+Redis; idempotency keys; dead-letter queue |
| 6 | Trace content | **Environment-dependent redaction:** full capture in dev; scrubbed in staging; minimal in prod |
| 7 | Git hooks | **Org-managed (enterprise):** IT deploys signed hook bundle; developers cannot bypass via env flag |
| 8 | Review scope | **Spec and code gaps:** changes must align documented intent with implemented behaviour |

---

## Summary of Change Types

| Type | Count (approx.) |
|------|-----------------|
| Modify existing sections | 18 |
| Add new sections (§23–§30) | 8 |
| Deprecate or reframe | 6 |
| Deliverables checklist refresh (§22) | 1 major update |

---

## §1 — Purpose

### Change 1.1 — Reframe framework scope as two layers

**Current:** SPECS describes a single-install dev lifecycle package only.

**Required change:** Split purpose into:

- **Layer 1 — Dev Lifecycle:** IDE guardrails, git hooks, local/hybrid LLM, PR evals, Knowledge Graph (retain).
- **Layer 2 — Production Runtime:** durable workflow orchestration, tenant-scoped deployment, LLM gateway, env-aware tracing (add).

Add explicit statement:

> AgenticFramework equips each tenant application to deploy itself. It does not deploy customer applications from a shared platform repository.

**Rationale:** Review confirmed runtime target C (dev locally + prod in cloud). Current SPECS stops at dev machine boundary; oil-price walkthrough implies production agents without specifying runtime infrastructure.

### Change 1.2 — Remove "shareable across repos" for golden evals in production

**Current (§1, line ~18):** "evaluation framework with golden datasets … shareable across repos"

**Required change:** Clarify that framework baseline evals are **bootstrap-only**. Production quality gates use **tenant-local** golden datasets only.

**Rationale:** Independent tenant model (B) — Acme and Beta have different app natures; shared production eval gates would block or mis-calibrate unrelated projects.

### Change 1.3 — Replace global hook default with dual install modes

**Current (§1, line ~16):** "Git lifecycle hooks … applied globally across all repositories"

**Required change:** Document two install modes:

| Mode | Audience | Hook behaviour |
|------|----------|----------------|
| `developer` | Solo / small team | Opt-in per repo via `.agenticframework/enabled` |
| `enterprise` | Org-managed | IT-deployed signed bundle; bypass disabled |

**Rationale:** Decision 7 (C) — enterprise IT pushes hooks; global `init.templateDir` affecting every repo is incompatible with org-controlled rollout.

---

## §2 — Guiding Principles

### Change 2.1 — Add new principles

**Required additions:**

| Principle | Description |
|-----------|-------------|
| **Tenant Isolation** | Each customer application is an independent repository with isolated promotion, evals, config, and runtime partition key (`tenant.id`). |
| **Environment Safety** | Trace and log content policy varies by `$ENVIRONMENT`; production never stores raw secrets or PII in observability backends by default. |
| **Durable Execution** | Production agent workflows must survive process crash, deploy, and network failure via external checkpointing and idempotent activities. |
| **Framework ≠ Application** | AgenticFramework releases on its own semver; tenant apps pin and upgrade independently. |

**Rationale:** Current principles cover code quality and HITL but not tenancy, production durability, or framework/application release separation — all confirmed requirements.

---

## §3 — System Architecture

### Change 3.1 — Replace single-box diagram with two-layer diagram

**Current:** One "Developer Workstation" box containing entire stack.

**Required change:** Add second diagram (or extend existing) showing:

```
Layer 1: Developer Workstation (existing content)
         │
         │  OTel contract + agent identity + tenant.id
         ▼
Layer 2: Production Runtime
         ├── Workflow engine (Temporal / Celery)
         ├── LLM Gateway (tenant-scoped routing + budgets)
         ├── Worker pool(s) — partitioned by tenant.id
         ├── Ops Portal (aggregates independent tenant pipelines)
         └── Phoenix (federated traces, filter by tenant.id)
```

**Rationale:** Architecture must visually communicate that production is a distinct layer, not an extension of the laptop install.

### Change 3.2 — Add production runtime components to inventory reference

**Required change:** Cross-reference new §25 (Production Runtime) from architecture section. List: `runtime/worker.py`, `runtime/workflows/`, `runtime/llm_gateway.py`, `runtime/trace_redactor.py`.

**Rationale:** §5 Component Inventory omits all production runtime files; diagram and inventory must stay aligned.

---

## §4 — Ten Operational Pillars

### Change 4.1 — Pillar 1: Enforce RFC at hook level (enterprise)

**Current:** RFC compliance is IDE instruction only; pre-commit (§5.2) does not verify spec existence.

**Required change:** Add enterprise hook rule:

- Staged source changes must map to an open RFC file in `.agent-rfc/`, **or** commit message must include `RFC-NNN` reference resolvable to a spec.
- Violation blocks commit in enterprise mode.

**Rationale:** Soft RFC enforcement is a security/governance gap; org-managed hooks (7C) can enforce what IDE rules alone cannot guarantee.

### Change 4.2 — Pillar 3: Add environment-aware span content policy

**Current (§4, Pillar 3):** Spans must carry `input.value`, `output.value` unconditionally.

**Required change:** Replace with:

| Environment | Span content policy |
|-------------|---------------------|
| `development` | Full `input.value` / `output.value` (up to 1,000 chars, current behaviour) |
| `staging` | Redacted — secrets/PII patterns stripped; structure preserved |
| `production` | Minimal — hashed or truncated; full payload only in encrypted HITL blob when case opened |

Reference new §27 (Trace Redaction).

**Rationale:** Decision 6C — environment-dependent capture; current spec mandates full prompt logging in all environments.

### Change 4.3 — Pillar 8: Fix hybrid data-locality claim

**Current (§8, Hybrid Cloud Mode, line ~393):** "Traces stream to local Phoenix (data never leaves the machine)"

**Required change:** Split into two explicit statements:

- **Trace data:** Stored at `AGENT_PHOENIX_ENDPOINT` (local or team server).
- **Inference data:** Cloud LLM calls transmit prompts to provider APIs in hybrid mode.

**Rationale:** Current wording is misleading; cloud inference necessarily leaves the machine even when traces stay local.

### Change 4.4 — Pillar 9: Scope orchestration to dev vs prod

**Current:** LangGraph `multi_agent_system.py` with `MemorySaver` presented as the orchestration solution.

**Required change:**

| Context | Orchestration backend |
|---------|----------------------|
| Dev / IDE sessions | LangGraph + `MemorySaver` or `local_agent_stack.py` (retain) |
| Production | Temporal workflow (preferred) or Celery task chain; **MemorySaver prohibited in prod** |

Add note: domain agent topologies (e.g. ingestion → prediction → decision → order) are defined **in each tenant repo**, not in the framework.

**Rationale:** Decision 5C requires durable queue + idempotency + DLQ; in-memory LangGraph checkpoints cannot satisfy long-running production agents.

### Change 4.5 — Pillar 10: Restrict cost router to dev; mandate gateway in prod

**Current:** `cost_router.py` is the universal routing mechanism.

**Required change:**

- **Dev:** `cost_router.py` keyword + token heuristics (retain, document limitations).
- **Prod:** All LLM calls route through **LLM Gateway** (§29) with per-model pricing, per-tenant budget, and degrade path (throttle → downgrade → queue → halt).

**Rationale:** Cost router is not wired into IDEs and uses brittle heuristics; production multi-LLM routing needs centralized enforcement and accurate per-model accounting.

---

## §5 — Component Inventory

### Change 5.1 — Standardize Claude Code config filename

**Current:** References `.claudecode.json` throughout (§5.3, §13, §14, §20).

**Required change:** Standardize on `CLAUDE.md` (matches `install-ai-stack.sh` implementation). Remove `.claudecode.json` references or mark deprecated with migration note.

**Rationale:** Spec/code inconsistency (review item 8C); installer writes `CLAUDE.md`, not `.claudecode.json`.

### Change 5.2 — Standardize Knowledge Graph path

**Current (§5.5):** `.agent-rfc/fixtures/knowledge_graph.json`

**Implementation (`local_knowledge_graph.py`):** `.agent-rfc/knowledge_graph.json`

**Required change:** Pick one path (recommend `.agent-rfc/fixtures/knowledge_graph.json` for consistency with other fixtures) and add migration in `post-checkout` hook.

**Rationale:** Path mismatch causes silent graph re-seeding and lost dependency data on upgrade.

### Change 5.3 — Extract hooks from installer to `hooks/` directory

**Current (§5.1, §16):** Hook templates listed under `hooks/` in repo structure; actual hooks are heredocs inside `install-ai-stack.sh`.

**Required change:** SPECS repo structure must match reality: either extract hooks to `hooks/` (preferred) or update §16 tree to show hooks embedded in installer with build step producing org bundle.

**Rationale:** Org-managed hook bundle (7C) requires versioned, signable hook artifacts — not inline installer strings.

### Change 5.4 — Add production runtime components

**Required new entries in §5.4:**

| File | Purpose |
|------|---------|
| `runtime/llm_gateway.py` | Prod LLM routing, per-model pricing, tenant budget enforcement |
| `runtime/trace_redactor.py` | Environment-aware OTLP span scrubbing before export |
| `runtime/worker.py` | Temporal/Celery worker entrypoint |
| `runtime/workflows/*.py` | Example durable workflows (reference only; tenant repos own prod definitions) |
| `runtime/idempotency.py` | Idempotency key store and dedup |
| `runtime/dead_letter.py` | Failed task queue and replay API |

**Rationale:** Component inventory must cover Layer 2 production stack.

### Change 5.5 — Add ops portal and in-app widget components

**Required new entries:**

| Path | Purpose |
|------|---------|
| `portal/` | Next.js (or equivalent) ops dashboard — multi-tenant pipeline view, cost, queue depth, unresolved log entries |
| `templates/in-app-widget/` | Embeddable trace status component for tenant applications |

**Rationale:** Decision 2D requires three observability surfaces; SPECS currently covers Phoenix only.

### Change 5.6 — Update `ai-stack-off` behaviour for enterprise mode

**Current (§6):** `ai-stack-off` sets `DISABLE_AI_STACK=true` and mutes hooks.

**Required change:** Document that `ai-stack-off` is **disabled in enterprise mode**. Emergency bypass requires IT break-glass procedure with audit log entry.

**Rationale:** Decision 7C — developers cannot bypass org hooks via environment variable.

---

## §6 — Shell Command Interface

### Change 6.1 — Add tenant lifecycle commands

**Required new commands:**

| Command | Action |
|---------|--------|
| `ai-tenant-init <id> [--stack STACK]` | Scaffold tenant repo with `.agenticframework/tenant.yaml`, CI/CD templates, metadata |
| `ai-tenant-promote <id> --from <env> --to <env>` | Promote deployment within **same tenant repo** (staging → production) |
| `ai-stack-upgrade [--to VERSION]` | Upgrade vendored framework scripts in current repo to pinned version |
| `ai-stack-uninstall` | Enterprise-safe removal of machine-level install (restore git templateDir) |

**Rationale:** Independent tenant model requires explicit tenant scaffolding and per-repo promotion CLI; no cross-tenant promotion exists.

### Change 6.2 — Add install mode flag

**Required change to §7 install invocation:**

```bash
./install-ai-stack.sh --mode developer   # default
./install-ai-stack.sh --mode enterprise  # org bundle, no global templateDir mutation
```

**Rationale:** Dual install modes (Change 1.3) need a documented entry point.

---

## §7 — Installation Procedure

### Change 7.1 — Document enterprise org bundle delivery

**Required addition:** Enterprise install produces:

- Signed hook tarball (`agenticframework-hooks-<version>.tar.gz`)
- MDM/deploy script template for IT
- Org policy file (`agenticframework-org.yaml`): hook version pin, bypass policy, Phoenix endpoint, SSO config

**Rationale:** Decision 7C — IT pushes hooks; install cannot rely on each developer mutating `~/.zshrc` and global git config unsupervised.

### Change 7.2 — Replace `curl | bash` as sole install method

**Required change:** Add signed release artifacts with checksum verification. Document internal registry option for enterprise. Retain `curl | bash` for developer mode with checksum gate.

**Rationale:** Supply-chain risk flagged in security review; enterprise compliance (4C optional) expects verifiable artifacts.

### Change 7.3 — Remove `ai-stack-on` reference if not implemented

**Current (§7, line ~335):** `source ~/.zshrc && ai-stack-on`

**Required change:** Verify command exists in installer; if not, replace with `ai-stack-status` or define `ai-stack-on`.

**Rationale:** Spec/code gap (8C) — undocumented or missing command breaks install procedure.

---

## §8 — Multi-Agent Execution Modes

### Change 8.1 — Add "Production Mode" subsection

**Required new subsection after Hybrid Cloud Mode:**

**Production Mode (tenant cloud):**

- Workflow engine: Temporal (recommended) or Celery + Redis
- Checkpointer: Postgres (Temporal) or Redis; never `MemorySaver`
- Scheduling: per-tenant cron defined in tenant repo config
- HITL pause: workflow signal + Phoenix annotation poll with timeout and DLQ on expiry
- Worker isolation: shared pool with `tenant_id` partition; dedicated pool when `tenant.isolation: dedicated`

**Rationale:** §8 covers local and hybrid dev modes only; production mode is the primary gap for long-running multi-agent apps.

---

## §9 — Evaluation Framework

### Change 9.1 — Remove shared production golden dataset merge

**Current (§9, "Golden Dataset — Dual Purpose"):** Framework base cases merge with project cases at eval time; shared calibration path implied.

**Required change:**

| Phase | Golden dataset source | Gate behaviour |
|-------|----------------------|----------------|
| Greenfield bootstrap | Copy from `~/.agent-framework/shared/golden_evals_base.json` once | Warning only — gate inactive |
| Before staging promotion | Tenant-authored cases required (minimum threshold) | Gate active for staging deploy |
| Production | Tenant-local cases + HITL-promoted cases from **that tenant's** prod traces only | Gate active for production deploy |

Remove language implying cross-repo or cross-tenant golden dataset sharing in production gates.

**Rationale:** Independent tenant model (B) — each project's eval suite reflects that project's task distribution only.

### Change 9.2 — Fix greenfield gate inconsistency

**Current conflict:**

- §9 table (line ~515): "Greenfield (0 cases) — CI skips eval step with warning"
- §9 (line ~507): "framework base cases activate quality gate immediately"

**Required change:** Single policy — framework base seeds file on init but **does not fail CI** until tenant-specific minimum case count reached (recommend: 3 tenant-authored or HITL-promoted cases before staging gate).

**Rationale:** Readme and SPECS contradict each other; causes unpredictable CI behaviour on new repos.

### Change 9.3 — Replace FIFO 10-rule cap with versioned criteria

**Current (§9, §5.5):** `historical_learnings` capped at 10 entries (FIFO eviction).

**Required change:**

- Version `custom_judge_criteria.json` with semver
- Semantic deduplication before append
- No silent FIFO eviction — archive evicted rules to `custom_judge_criteria.archive.json` with timestamp and reason

**Rationale:** Production self-improvement at scale loses valuable lessons under FIFO cap; tenant apps accumulate distinct rule sets over time.

### Change 9.4 — Add shadow eval specification

**Required addition:**

- Async sample (default 5%) of production traces evaluated by LLM judge post-hoc
- Results written to Phoenix experiments; do not block user-facing workflow
- Feeds suggested promotion queue in ops portal

**Rationale:** HITL-only promotion does not scale; shadow evals detect regressions before human review.

### Change 9.5 — CD golden-dataset commits must use PR

**Current (§17, cd-deploy.yml pattern):** Bot commits directly to `main` with `[skip ci]`.

**Required change:** Bot opens PR in **same tenant repo**; production promotion of fixture changes requires review. Remove `[skip ci]` bypass for eval fixture updates.

**Rationale:** Independent tenant repos still need governance on self-improvement artifacts; direct push to `main` bypasses branch protection intent.

---

## §10 — Knowledge Graph

### Change 10.1 — No cross-tenant graph federation

**Current (§14):** Shared RFC store via `AGENT_SHARED_RFC_DIR` optional.

**Required change:** Clarify `AGENT_SHARED_RFC_DIR` is for **documentation sharing within one org**, not cross-tenant production linkage. Knowledge Graph remains strictly per-repo. Remove any implication that subgraph context spans tenant boundaries.

**Rationale:** Tenant apps are independent; shared graph edges across tenants would create incorrect agent context.

---

## §11 — Financial Circuit Breaker

### Change 11.1 — Replace `sys.exit(1)` with tiered degrade

**Current (§11):** Breach → `RuntimeError` → `sys.exit(1)` → all cloud execution halts.

**Required change — degrade ladder:**

1. Throttle request rate
2. Downgrade to cheaper model tier via LLM Gateway
3. Queue tasks with delay
4. Halt cloud inference (local fallback if available)
5. Alert via Slack/Teams + ops portal

Production workers must **not** terminate the worker process on budget breach.

**Rationale:** Hard kill disrupts long-running workflows mid-execution; Temporal activities need graceful handling and retry semantics.

### Change 11.2 — Budget hierarchy

**Current:** Repo-level `token_velocity_cache.json` and machine-level `machine_budget.json` — relationship unclear.

**Required change — explicit hierarchy:**

```
org cap (enterprise, optional)
  └── tenant cap (per tenant.id)
        └── workflow cap (per workflow type)
              └── session cap (dev IDE sessions, existing burst window)
```

Document which file/store backs each level. Production budgets enforced in LLM Gateway; dev budgets in `circuit_breaker.py`.

**Rationale:** Independent tenants need isolated budgets; flat $150/month repo default is wrong for multi-tenant ops.

### Change 11.3 — Per-model pricing table

**Current:** Single blended input/output token rate.

**Required change:** `models.yaml` per tenant repo (override) with framework defaults; gateway computes cost per span using actual model id.

**Rationale:** Cost router uses inaccurate flat rates; ops portal cost dashboard requires per-model accuracy.

---

## §14 — Multi-Repository Support

### Change 14.1 — Reframe as "Multi-Tenant Independent Repositories"

**Current title and content:** Multi-repo and monorepo support with shared team configuration.

**Required change:** Reframe section:

- **Framework repo:** AgenticFramework tooling (single GitHub repo, own release cycle)
- **Tenant repos:** One repo per customer application — independent nature, stack, agents, promotion
- **Monorepo:** Still supported **within one tenant** (sub-package `.agent-rfc/` scoping retained)

Add:

> There is no shared customer application trunk. Tenant A production may run commit `abc` while Tenant B production runs commit `def`.

**Rationale:** Core architectural decision B must be the organising concept for §14, not an afterthought.

### Change 14.2 — Add `.agenticframework/tenant.yaml` schema

**Required new schema:**

```yaml
tenant:
  id: acme
  name: Acme Corp
  isolation: shared          # shared | dedicated
framework:
  version: "1.2.0"           # pinned AgenticFramework version
  mode: enterprise
environments:
  development: { phoenix_namespace: acme-dev }
  staging:     { phoenix_namespace: acme-staging }
  production:  { phoenix_namespace: acme-prod }
```

**Rationale:** Tenant identity must be declarative and version-controlled per repo, not inferred from directory name alone.

### Change 14.3 — Update shared vs per-repo data table

**Current (§14 table):** Golden baseline at `~/.agent-framework/shared/` merged at eval time for all projects.

**Required change:**

| Data | Scope | Production use |
|------|-------|----------------|
| `golden_evals_base.json` | Framework install | Bootstrap copy only; not merged in prod gate |
| `golden_evals.json` | Tenant repo | Sole source for staging/production gates |
| `custom_judge_criteria.json` | Tenant repo | Tenant-local only |
| `machine_budget.json` | Machine / org | Dev sessions only |
| Tenant budget | LLM Gateway store | Production enforcement |

**Rationale:** Aligns data scoping with independent tenant promotion model.

---

## §15 — Universal Observability Platform

### Change 15.1 — Add mandatory `tenant.id` span attribute

**Current attributes:** `project.name`, `project.repo`, `environment`, `ai_stack_mode`

**Required addition:**

| Attribute | Source | Example |
|-----------|--------|---------|
| `tenant.id` | `.agenticframework/tenant.yaml` | `acme` |
| `tenant.name` | `.agenticframework/tenant.yaml` | `Acme Corp` |

All scripts (`agent_logger.py`, runtime workers, IDE OTel wire) must emit these.

**Rationale:** Federated ops portal and independent tenant pipelines require consistent tenant filtering in Phoenix.

### Change 15.2 — Add Ops Portal specification

**Required new subsection §15.x — Ops Portal:**

- **Purpose:** Cross-tenant operations view aggregating independent pipelines
- **Views:** tenant list, deploy status per env, cost by tenant/agent/model, queue depth, unresolved MAJOR/CRITICAL, suggested HITL promotion queue
- **Auth:** SSO/OIDC when enterprise pack enabled; role-based access (viewer, operator, admin)
- **Data sources:** Phoenix API, workflow engine metrics, LLM Gateway spend, `.agent-history.log` sync

**Rationale:** Decision 2D — Phoenix alone is insufficient for multi-tenant ops at independent promotion scale.

### Change 15.3 — Add In-App Observability Widget specification

**Required new subsection §15.x — In-App Widget:**

- Embeddable component (React/Vanilla) shipped in `templates/in-app-widget/`
- Shows: last agent run status, link to tenant-scoped Phoenix trace, error summary
- Read-only; tenant-scoped auth token; no cross-tenant data

**Rationale:** Decision 2D — end users of tenant applications need visibility without ops portal access.

### Change 15.4 — Phoenix auth mandatory for team mode

**Current:** Reverse proxy + TLS in `docs/team-observability.md` referenced as optional.

**Required change:** Team-shared and production Phoenix **must** require authentication. Update `docker-compose.yml` spec to include auth sidecar (Caddy + OAuth or basic auth at minimum). Unauthenticated team Phoenix is non-compliant.

**Rationale:** Production traces may contain sensitive metadata even with redaction; team Phoenix without auth is a security gap.

---

## §16 — GitHub Repository

### Change 16.1 — Add framework CI workflow to repo structure

**Current (§16, §22):** Lists `.github/workflows/release.yml` and `self-test.yml` as deliverables.

**Required change:** SPECS must require these files exist and gate framework releases. Add `self-test.yml` running `verify_system.py` + hook template lint + schema validation for `tenant.yaml`.

**Rationale:** §22 marks deliverables pending; framework itself lacks CI while mandating CI for tenant repos (8C).

### Change 16.2 — Add `examples/` directory to repo structure

**Required addition:**

```
examples/
├── oil-price-agent/     # Reference tenant app (fork per customer)
└── README.md            # "Copy and rename — do not deploy from framework repo"
```

**Rationale:** Walkthrough in Readme implies production app but framework repo should not be the deployment source for customer apps under model B.

### Change 16.3 — Add `agent-rules.yaml` single source for IDE configs

**Required addition to templates:**

```
templates/
├── agent-rules.yaml          # Single source
├── generated/                # Built by post-checkout
│   ├── cursorrules/
│   ├── CLAUDE.md
│   └── antigravity/skills/
```

**Rationale:** Three parallel rule files drift; maintenance burden violates ease-of-changes requirement.

---

## §17 — CI/CD via GitHub Actions

### Change 17.1 — Split CD into per-environment workflows

**Current:** Single `cd-deploy.yml` on push to `main`.

**Required change — per tenant repo template set:**

| Workflow | Trigger | Environment | Gate |
|----------|---------|-------------|------|
| `ci-<stack>.yml` | PR to `develop` or `main` | — | lint, test, evals (dev profile) |
| `cd-staging.yml` | Push to `develop` | staging | eval `--fail-below` + smoke |
| `cd-production.yml` | Push to `main` | production | eval `--fail-below` + smoke; **no `continue-on-error`** |

Remove single-hop `main`-only CD as the default pattern.

**Rationale:** Decision 3 — within each independent tenant repo, promotion follows develop → staging → production (A), applied per tenant (B).

### Change 17.2 — Remove cross-tenant deployment assumptions

**Current:** CD workflow language implies org-wide production deploy.

**Required change:** All workflow templates include header comment:

```yaml
# Tenant-scoped CD — applies to THIS repository only.
# tenant.id: {{TENANT_ID}}
```

Workflows must not reference org-level shared secrets beyond this tenant's GitHub Environment.

**Rationale:** Independent tenant repos deploy independently; workflow prose must not imply platform-wide release.

### Change 17.3 — Add rollback step on failed production smoke

**Current:** Post-deploy eval uses `continue-on-error: true`.

**Required change:**

- Production smoke failure → fail job → invoke platform rollback hook (documented extension point per deploy target: Fly, Railway, ECS, etc.)
- Staging smoke failure → block promotion to `main`

**Rationale:** Self-improvement loop is undermined if bad deploys stay live; `continue-on-error` contradicts March of Nines principle.

### Change 17.4 — Per-environment secrets and eval thresholds

**Required addition:**

| Environment | `ENVIRONMENT` var | Eval threshold | Redaction profile |
|-------------|-------------------|----------------|-------------------|
| CI / PR | `development` | warn below 0.7 | none |
| Staging deploy | `staging` | fail below 0.75 | staging |
| Production deploy | `production` | fail below 0.80 | production |

**Rationale:** Single threshold for all environments does not match independent promotion gates or redaction policy (6C).

---

## §18 — Agent Identity

### Change 18.1 — Add tenant and workflow identity dimensions

**Required additions to identity table:**

| Dimension | Attribute key | Source |
|-----------|---------------|--------|
| Tenant ID | `tenant.id` | `.agenticframework/tenant.yaml` |
| Workflow ID | `workflow.id` | Temporal workflow id or Celery task id |
| Workflow run | `workflow.run_id` | Engine-assigned run identifier |
| Idempotency key | `workflow.idempotency_key` | Activity input hash |

**Rationale:** Production runtime (5C) requires trace linkage from Phoenix span → workflow → tenant for debugging long-running multi-agent jobs.

### Change 18.2 — HITL RBAC

**Required addition:**

- `promoted_by` must match allowlist (SSO group or explicit list in tenant config)
- Enterprise pack: promotion actions logged to immutable audit trail

**Rationale:** Optional enterprise compliance (4C) requires knowing who approved promotions; any Phoenix user can currently annotate.

---

## §19 — Structured Agent History Log

### Change 19.1 — Sync log entries to ops portal

**Required change:** `.agent-history.log` MAJOR/CRITICAL entries synced to ops portal unresolved queue (in addition to `ai-stack-check` local summary).

**Rationale:** Independent tenant ops cannot rely on each developer running `ai-stack-check` locally; centralized visibility required.

---

## §20 — IDE Config Security

### Change 20.1 — Extend public repo check to `tenant.yaml`

**Required change:** When auto-gitignore triggers for public repos, also prompt to gitignore `.agenticframework/tenant.yaml` if it contains non-public tenant metadata.

**Rationale:** Tenant config may expose customer identifiers on public repos.

---

## §21 — Resolved Design Decisions

### Change 21.1 — Append decisions from architecture review

**Required new rows:**

| # | Topic | Decision |
|---|-------|----------|
| 12 | Runtime topology | Dual layer: dev lifecycle on workstation; production runtime in cloud |
| 13 | Tenancy | Independent repo per tenant (B); no shared customer main |
| 14 | Promotion | Per tenant repo: develop → staging → production |
| 15 | Durable execution | Temporal (preferred) or Celery+Redis in production; MemorySaver dev-only |
| 16 | Observability surfaces | Phoenix + ops portal + in-app widget |
| 17 | Trace redaction | Environment-dependent: full dev, scrubbed staging, minimal prod |
| 18 | Hook deployment | Enterprise org-managed signed bundle; bypass disabled |
| 19 | LLM routing | cost_router dev-only; LLM Gateway mandatory in production |
| 20 | Golden evals | Tenant-local for gates; framework base bootstrap-only |
| 21 | Enterprise pack | Optional: SSO, audit trail, dedicated tenant isolation, compliance |

**Rationale:** §21 is the decision log; review conclusions must be recorded to prevent re-litigation.

---

## §22 — Deliverables Checklist

### Change 22.1 — Refresh entire checklist

**Current:** Most items marked "Pending" despite partial implementation.

**Required change:** Replace with phased checklist reflecting actual state and new scope:

**Phase 0 — Spec alignment**
- [ ] Apply all changes in this document to SPECS.md
- [ ] Fix `.claudecode.json` → `CLAUDE.md` across all docs
- [ ] Standardize knowledge graph path + migration
- [ ] Fix hybrid data-locality wording in Readme and SPECS

**Phase 1 — Tenant scaffold**
- [ ] `.agenticframework/tenant.yaml` schema and `ai-tenant-init`
- [ ] Per-tenant CI/CD workflow templates (ci + cd-staging + cd-production)
- [ ] `tenant.id` wired into all OTel spans and logs

**Phase 2 — Production runtime**
- [ ] `runtime/` package (worker, gateway, redactor, idempotency, DLQ)
- [ ] Temporal reference workflow in `examples/oil-price-agent/`
- [ ] Postgres checkpointer; MemorySaver marked dev-only in docs

**Phase 3 — Observability**
- [ ] Ops portal v1
- [ ] In-app widget template
- [ ] Phoenix auth in docker-compose default

**Phase 4 — Enterprise pack (optional)**
- [ ] Org hook bundle signing and MDM deploy script
- [ ] SSO for portal and Phoenix
- [ ] Immutable audit log
- [ ] Dedicated worker pool per tenant (`isolation: dedicated`)

**Phase 5 — Framework hygiene**
- [ ] Extract hooks to `hooks/` directory
- [ ] `.github/workflows/self-test.yml` and `release.yml`
- [ ] `agent-rules.yaml` single-source IDE config generation
- [ ] `ai-stack-uninstall` command

**Rationale:** Current §22 is stale and omits production runtime, tenancy, portal, and enterprise deliverables entirely.

---

## New Sections to Add

### §23 — Tenancy Model (Independent Repositories)

**Content required:**

- Definition: one repo per customer application
- Framework repo vs tenant repo responsibilities
- `tenant.yaml` schema (full)
- Isolation tiers: `shared` vs `dedicated`
- Explicit non-goals: no cross-tenant merges, no shared production deploy

**Rationale:** Organising concept for model B; absent from current SPECS.

---

### §24 — Per-Tenant Lifecycle and Promotion

**Content required:**

- Branch → environment mapping within each tenant repo
- `ai-tenant-promote` semantics (same repo only)
- GitHub Environments per repo (`staging`, `production`)
- Fixture promotion via PR, not direct push
- Framework version pin and independent upgrade cadence

**Rationale:** §17 covers CI/CD generically but not independent per-tenant promotion as first-class design.

---

### §25 — Production Runtime

**Content required:**

- Workflow engine selection (Temporal recommended; Celery fallback)
- Worker topology and tenant partitioning
- Idempotency key design
- Dead-letter queue and replay procedure
- HITL pause/resume via workflow signals
- Scheduling (cron per tenant)
- Domain workflow ownership (tenant repo, not framework)

**Rationale:** Decision 5C; largest spec gap.

---

### §26 — Federated Observability

**Content required:**

- Three surfaces and their audiences (operator vs developer vs end user)
- Phoenix namespacing by `tenant.id`
- Ops portal data model and API
- In-app widget integration contract
- Cross-tenant aggregation without cross-tenant data leakage

**Rationale:** Decision 2D.

---

### §27 — Trace Redaction

**Content required:**

- Redaction profiles per environment
- `trace_redactor.py` integration point (pre-OTLP export)
- Encrypted HITL blob specification (when/who/how long)
- Secret/PII pattern library (extensible per tenant)
- CI validation: staging/prod profiles must never emit raw API keys (test fixture)

**Rationale:** Decision 6C; Pillar 3 currently mandates full prompt capture.

---

### §28 — Framework vs Application Release

**Content required:**

- AgenticFramework semver and release process
- Tenant pinning via `.agenticframework/tenant.yaml` `framework.version`
- Vendored scripts upgrade path (`ai-stack-upgrade`)
- Compatibility matrix (framework version × tenant stack)
- Explicit statement: examples are forked, not deployed from framework repo

**Rationale:** Independent tenants upgrade on their own schedule; must be documented to prevent coupling.

---

### §29 — LLM Gateway (Production)

**Content required:**

- Gateway API (sync + streaming)
- Model registry (`models.yaml` schema)
- Per-tenant routing overrides
- Per-model pricing and cost attribution on spans
- Budget enforcement and degrade ladder
- Mandatory gateway usage in production (enforcement mechanism)
- Relationship to dev-mode `cost_router.py`

**Rationale:** Multi-LLM in production with cost optimisation requires centralized prod routing distinct from dev heuristics.

---

### §30 — Enterprise Install and Compliance Pack

**Content required:**

- Org hook bundle format, signing, deployment
- Bypass policy and break-glass audit
- SSO integration points (portal, Phoenix, GitHub)
- Immutable audit log schema (promotions, config changes, bypass events)
- Dedicated infrastructure provisioning for `isolation: dedicated`
- Compliance mappings (SOC2-oriented control notes — optional enablement)

**Rationale:** Decisions 4C and 7C; optional but must be spec'd for enterprise path.

---

## Items to Deprecate or Remove from SPECS

| Location | Current content | Action | Rationale |
|----------|----------------|--------|-----------|
| §8 Hybrid mode | "data never leaves the machine" | **Remove / rewrite** | Factually incorrect for cloud inference |
| §9 | Framework base golden merged at prod eval time | **Remove from prod path** | Tenant-local gates only (B) |
| §11 | `sys.exit(1)` on budget breach | **Replace** with degrade ladder | Incompatible with durable workflows |
| §6 | `ai-stack-off` mutes hooks unconditionally | **Restrict** to developer mode | Enterprise org-managed hooks (7C) |
| §17 | Single `cd-deploy.yml` on `main` | **Replace** with cd-staging + cd-production | Per-tenant develop→staging→prod (A+B) |
| §17 | `continue-on-error: true` on prod eval | **Remove** | Must block or rollback bad deploys |
| §5.3 / §13 / §14 | `.claudecode.json` | **Deprecate** → `CLAUDE.md` | Spec/code mismatch |
| §14 | Implied shared team golden dataset in prod | **Remove** | Independent tenant evals |

---

## Cross-Document Updates (Readme.md — out of scope but referenced)

SPECS changes will require corresponding Readme updates. Flag for follow-up:

| Readme section | SPECS-driven change |
|----------------|---------------------|
| "What It Sets Up" table | Add Production Runtime, Ops Portal, Tenant scaffold rows |
| Oil price walkthrough Step 9 | Clarify production runs on cloud runtime, not laptop Phoenix |
| Quick Start | Add `--mode enterprise` and `ai-tenant-init` |
| Configuration table | Add `tenant.id`, gateway URL, redaction profile vars |
| Execution Modes | Add Production Mode subsection |

---

## Document Metadata Update

When changes are applied to SPECS.md, update header:

```markdown
**Version:** 0.4.0-draft
**Date:** 2026-06-22
**Status:** Draft — incorporates tenancy, production runtime, and observability review
```

---

## Application Order

Recommended sequence for applying changes to SPECS.md:

1. **§1, §2, §21** — Decisions and principles (sets context for all other edits)
2. **§23–§30** — New sections (add before renumbering conflicts)
3. **§3, §5, §8** — Architecture and components
4. **§14, §15, §17** — Tenancy, observability, CI/CD
5. **§4, §9, §11, §18** — Pillars and cross-cutting policies
6. **§6, §7, §16, §19, §20, §22** — Commands, install, deliverables
7. **Readme.md** — Align public-facing doc

---

*Generated from architecture review session. Apply to SPECS.md via dedicated edit PR.*
