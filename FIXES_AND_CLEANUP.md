# AgenticFramework — Implementation PR Backlog

**Last reviewed:** 2026-06-22 (against OPERATIONS.md, SPECS.md, and full codebase)  
**Purpose:** Actionable implementation PRs for remaining gaps (P0–P5).

---

## Completed — redundancy cleanup (2026-06-22)

| Change | PR scope |
|--------|----------|
| `hooks/post-checkout` copies `workflow-templates/` (removed ~130 lines of inline CI/CD heredocs) | Single source for CI/CD with `ai-tenant-init` |
| Deleted `workflow-templates/cd-deploy.yml` | Superseded by `cd-staging.yml` + `cd-production.yml` |
| Removed legacy `templates/cursorrules/`, `templates/claude/`, `templates/antigravity/` | IDE output from `agent-rules.yaml` only |
| Archived `specs-update.md` → `docs/archive/` | Merged into SPECS.md |
| Root `.gitignore` | Ignores `portal/.next/`, `node_modules/`, etc. |
| Updated `UserManual.md`, `SPECS.md` repo tree | Stale `cd-deploy.yml` references removed |

Legacy repos with `.github/workflows/cd-deploy.yml` get a warning on next `post-checkout` — delete that file manually and rely on `cd-staging.yml` / `cd-production.yml`.

---

## Resolved (no PR needed)

The original adversarial review (Part 1–2, much of Part 4) has been implemented. Do not re-open these unless a regression is found.

| ID | Topic | Resolution |
|----|-------|------------|
| 1.1 | Portal RBAC | `portal/lib/authz.ts`, middleware headers, route checks, `portal/test/authz.test.ts` |
| 1.2 | Per-span tenant in redactor | `TraceRedactor.on_end()` reads `tenant.id` from span attrs |
| 1.3 | `cost_router` in `runtime/` | Enterprise pre-commit guard in `hooks/pre-commit` |
| 1.4 | `ai-tenant-promote` substring match | Exact YAML field parse in `install-ai-stack.sh` |
| 1.5 | Break-glass token validation | `_ai_validate_break_glass_token` HMAC + expiry |
| 1.6 | Audit log silent drop | `~/.agent-framework/local-audit-fallback.log` on portal write failure |
| 2.1 | Budget race | Atomic `try_reserve()` in `runtime/llm_gateway.py` |
| 2.2 | HITL blob key collision | `{trace_id}.{span_id}.{attr_key}` in `trace_redactor.py` |
| 2.6 | Middleware auth matcher | Segment-boundary exclusions in `portal/middleware.ts` |
| 2.7 | Widget token revoke | `DELETE /api/tenants/:id/widget-token` |
| 2.8 | `ENVIRONMENT` inconsistency | Shared `runtime/environment.py` fail-closed resolver |
| 2.4 | Audit FK | `audit_log.tenant_id REFERENCES tenants(tenant_id)` in `portal/db/schema.sql` |
| 2.5 | `isolation` enum | `CHECK (isolation IN ('shared', 'dedicated'))` + route validation |
| 4.1 | Duplicated eval CI block | Reusable `workflow-templates/eval-scorecard.yml` |
| 4.2 | Middleware duplicates OIDC | Uses `verifySessionToken` from `portal/lib/sessionToken.ts` |
| 4.3 | Provider dispatch duplication | `runtime/provider_dispatch.py` shared by gateway + cost_router |
| 4.12 | Unsafe tenant id in sed | `^[a-z0-9-]+$` validation in `ai-tenant-init` |
| 4.14 | Session revocation | `revoked_sessions` table + logout flow |
| 4.15 | Budget period timezone | UTC via `time.gmtime()` in gateway; portal uses `toISOString()` |

**Partial (documented, not fully fixed):**

- **2.3 HITL blob I/O errors:** missing encryption key raises; transient storage failures log ERROR and may leave dangling `hitl_blob_ref` — see P2 optional hardening.
- **2.3 config vs I/O:** acceptable for v1; P2 can add retry queue.

---

## PR dependency graph

```
P0 (runtime stores) ──► P1 (hooks + CD sync) ──► P2 (portal v2)
                              │
                              └──► P3 (CI tests) — can start in parallel with P1
P4 (CD templates) — independent
P5 (hygiene) — independent, lowest priority
```

---

## P0 — Production runtime: idempotency, DLQ, worker wiring

**Branch:** `feat/runtime-persistent-stores`  
**Blocks:** Production multi-agent durability promise (SPECS.md §25, OPERATIONS.md §D.4)

### Problem

`runtime/idempotency.py` and `runtime/dead_letter.py` raise `NotImplementedError`. The Ops Portal DLQ view correctly reports `wired: false`. Duplicate LLM calls are not suppressed; failed activities cannot be replayed from a persistent queue.

### Scope

| File | Change |
|------|--------|
| `runtime/idempotency.py` | Implement `_PostgresBackend` and `_RedisBackend` (`get`/`set` with TTL) |
| `runtime/dead_letter.py` | Implement Postgres-backed `enqueue`, `list`, `replay`, `discard` |
| `portal/db/schema.sql` | Add `dlq_entries` + `idempotency_keys` tables (document column contract already in schema comments) |
| `runtime/llm_gateway.py` | Remove silent swallow on idempotency `NotImplementedError`; log cache miss vs hit |
| `runtime/workflows/base_workflow.py` | Call real `DeadLetterQueue.enqueue` on HITL timeout (replace no-op / raise path) |
| `examples/oil-price-agent/workflows/activities.py` | Emit idempotency keys on gateway calls |
| `scripts/verify_system.py` | Add `--check-idempotency` / `--check-dlq` against throwaway Postgres |
| `requirements.txt` | Pin `redis` if not present (optional backend) |

### Acceptance criteria

- [ ] `IDEMPOTENCY_BACKEND=postgres` + `DATABASE_URL`: second `complete()` with same key returns cached result without provider call
- [ ] `DeadLetterQueue.enqueue()` persists row; `GET /api/dlq` returns `wired: true` with correct `pendingByTenant` counts
- [ ] `replay(task_id)` re-enqueues to Temporal (example worker) or marks replayed with audit entry
- [ ] OPERATIONS.md §D.4 "Known gap" paragraph removed or replaced with setup instructions
- [ ] `docker run postgres:16` + pytest (new `runtime/test/test_stores.py`) passes in CI (see P3)

### Docs

- OPERATIONS.md §D.1–D.4, SPECS.md §25 TODOs

---

## P1 — Spec/code alignment: hooks, CD sync, shadow evals

**Branch:** `feat/spec-alignment-hooks-cd-shadow`  
**Depends on:** none (orthogonal to P0; merge order flexible)

### Problem

Several SPECS/OPERATIONS claims are not enforced in code: developer opt-in hooks, enterprise RFC pre-commit, automatic history sync in CD workflows, and shadow evals (SPECS.md §9) have no implementation.

---

### P1a — Developer opt-in + enterprise RFC hooks

| File | Change |
|------|--------|
| `hooks/pre-commit` | If org policy absent: require `.agenticframework/enabled` or `.agenticframework/tenant.yaml` or exit 0 (skip). If org policy present: require `RFC-NNN` in commit message **or** staged paths covered by open `.agent-rfc/*.md` |
| `hooks/post-commit`, `hooks/post-checkout`, `hooks/commit-msg` | Same opt-in gate at top (after `DISABLE_AI_STACK`) |
| `install-ai-stack.sh` | `ai-tenant-init` writes `.agenticframework/enabled` marker; document `--mode developer` vs enterprise MDM path |
| `scripts/verify_system.py` | `--check-hooks` simulates opt-in / RFC block |

**Acceptance criteria**

- [ ] Repo without `.agenticframework/enabled` and without org policy: hooks no-op
- [ ] Repo with `enabled` + org policy: commit without RFC reference blocked in enterprise mode
- [ ] SPECS.md §7 install modes match installer behaviour

---

### P1b — CD history sync to Ops Portal

| File | Change |
|------|--------|
| `scripts/sync-portal-history.py` | **New.** Parse `.agent-history.log` JSONL since last sync (`.agent-rfc/fixtures/sync_state.json`); POST to `OPS_PORTAL_URL/api/sync/history` |
| `workflow-templates/cd-staging.yml` | Optional step (when secrets present): run sync after deploy |
| `workflow-templates/cd-production.yml` | Same |
| `install-ai-stack.sh` | `ai-stack-check` calls sync when `OPS_PORTAL_*` env vars set |
| `templates/agent-rules.yaml` or tenant CD docs | Document required secrets: `OPS_PORTAL_URL`, `OPS_PORTAL_SYNC_TOKEN` |

**Acceptance criteria**

- [ ] Push to `develop` with secrets configured → portal shows tenant issues without manual curl
- [ ] Missing secrets → step skipped with warning (does not fail CD)
- [ ] `portal/app/api/sync/history/route.ts` comment matches reality

---

### P1c — Shadow eval sampler

| File | Change |
|------|--------|
| `scripts/shadow-eval.py` | **New.** Sample N% of Phoenix spans (filter `environment=production`); async LLM judge; write to Phoenix experiments with `eval.type=shadow` |
| `workflow-templates/cd-production.yml` | Optional nightly/cron workflow template `shadow-eval.yml` |
| `portal/lib/promotions.ts` | **New.** Read failed shadow scores → "suggested promotion" list on tenant page |
| `portal/app/tenants/[id]/page.tsx` | Render suggestions queue (read-only until HITL) |

**Acceptance criteria**

- [ ] `python3 scripts/shadow-eval.py --sample-rate 0.05` runs against team Phoenix without blocking prod
- [ ] Portal tenant detail shows ≥0 suggestions when shadow failures exist
- [ ] SPECS.md §9 shadow eval no longer spec-only

---

## P2 — Ops Portal v2: run status, cost cap, Phoenix depth

**Branch:** `feat/portal-run-status-phoenix`  
**Depends on:** P1b (history sync) for best widget fidelity; can merge without P1c

### Problem

Widget status is inferred from last history entry only (`portal/lib/runStatus.ts`). Cost cap always `null`. Phoenix integration is health-check + link only (`portal/lib/phoenix.ts`).

### Scope

| File | Change |
|------|--------|
| `portal/db/schema.sql` | `agent_runs` table: `run_id`, `tenant_id`, `workflow_id`, `status`, `started_at`, `finished_at`, `trace_id`, `error_summary` |
| `runtime/llm_gateway.py` | Optional callback/hook to record run start/end (or document HTTP POST to portal M2M endpoint) |
| `portal/app/api/runs/ingest/route.ts` | **New.** Bearer-token ingest (like sync/history) |
| `portal/lib/runStatus.ts` | Prefer `agent_runs`; fall back to history |
| `portal/lib/cost.ts` | Read `budget_cap_usd` from synced tenant metadata or env default |
| `portal/lib/phoenix.ts` | v1 GraphQL: fetch recent trace count / error rate for tenant filter |
| `templates/in-app-widget/README.md` | Document self-host `widget.js` until CDN exists (P5) |

### Acceptance criteria

- [ ] Widget can return `running` when an open run exists in `agent_runs`
- [ ] Tenant cost page shows cap + % used when `tenant.yaml` defines `gateway.budget_cap_usd`
- [ ] Tenant page shows Phoenix error rate (last 24h) when `phoenix_base_url` configured
- [ ] OPERATIONS.md §F "Known gap" updated

---

## P3 — CI behaviour tests (self-test expansion)

**Branch:** `feat/self-test-behaviour`  
**Depends on:** P0 for gateway/store tests; portal tests independent

### Problem

`.github/workflows/self-test.yml` only checks parse/build. OPERATIONS.md §9 lists `npm test`, redaction checks, and Postgres-backed tests — none run in CI.

### Scope

| File | Change |
|------|--------|
| `.github/workflows/self-test.yml` | Add jobs: `portal npm test`, `ENVIRONMENT=staging|production verify_system --check-redaction`, Postgres service + `runtime/test/` |
| `runtime/test/test_llm_gateway_budget.py` | **New.** Concurrent `try_reserve` cannot exceed cap |
| `runtime/test/test_trace_redactor.py` | **New.** API keys redacted in staging/production profiles |
| `portal/test/auditLog.test.ts` | **New.** HMAC sign/verify round-trip |
| `requirements.txt` | Add `pytest` explicitly |

### Acceptance criteria

- [ ] PR to `main` runs all new jobs green
- [ ] Regression in RBAC (`authz.test.ts`) fails CI
- [ ] Redaction regression fails CI

---

## P4 — CD/deploy templates and rollback scaffolding

**Branch:** `feat/cd-deploy-scaffolding`  
**Depends on:** none

### Problem

Deploy steps are placeholders. Rollback is echo-only. Legacy `cd-deploy.yml` confuses tenants. Platform-specific deploy is intentionally tenant-owned but needs clearer extension points.

### Scope

| File | Change |
|------|--------|
| `workflow-templates/cd-staging.yml` | Replace echo with composite input `deploy_command` (default: no-op + skip) |
| `workflow-templates/cd-production.yml` | Same; wire rollback composite on smoke failure |
| `.github/actions/deploy-placeholder/` | **New.** Documented no-op for greenfield |
| `.github/actions/rollback-notify/` | **New.** Slack/Teams + fail job (platform rollback remains tenant-supplied) |
| `workflow-templates/cd-deploy.yml` | **Deleted** — use `cd-staging.yml` + `cd-production.yml` |
| `OPERATIONS.md` | Section: "Wire your platform" with Fly/Railway/ECS examples |

### Acceptance criteria

- [x] `ai-tenant-init` never copies `cd-deploy.yml` (file removed from repo)
- [ ] Production smoke failure fails the workflow (already true) **and** runs rollback-notify action
- [ ] Tenant can set `DEPLOY_COMMAND` secret without editing workflow YAML

---

## P5 — Repo hygiene and remaining cleanup

**Branch:** `chore/repo-hygiene`  
**Depends on:** none

### Problem

Leftover cleanup items, doc drift, and workspace noise from the first review pass.

### Scope

| ID | File | Change |
|----|------|--------|
| 5.1 | `.gitignore` | **Done** — root ignore file added |
| 5.2 | `install-ai-stack.sh` | Parse `--mode developer\|enterprise`; enterprise skips global `init.templateDir` |
| 5.3 | `install-ai-stack.sh` | `ai-stack-upgrade`: check `git commit` exit code before success message (4.9) |
| 5.4 | `install-ai-stack.sh` | `ai-stack-scrub`: list exact paths before confirm prompt (4.11) |
| 5.5 | `hooks/post-commit` | Narrow Python except in log rotation (4.7); quoted heredoc for log path (4.8) |
| 5.6 | `portal/app/api/tenants/route.ts` | Static import for `upsertTenant` (4.6) |
| 5.7 | `scripts/cost_router.py` | Bound `_consecutive_failures` dict size (4.4) |
| 5.8 | `runtime/k8s/dedicated-tenant/configmap.yaml` | Comment accepted `BUDGET_BACKEND` / `WORKER_BACKEND` values |
| 5.9 | `.github/workflows/release.yml` | Extract + smoke-test tarballs before publish (4.13) |
| 5.10 | `Readme.md`, `install-ai-stack.sh` | Replace `<org>` with env-substitution or real org placeholder doc |
| 5.11 | `templates/in-app-widget/` | Add `npm run build` artifact to `release.yml` OR document self-host only (no `cdn.agenticframework.io` until hosted) |
| 5.12 | `runtime/worker.py` | Either delegate to example pattern doc **or** thin wrapper importing tenant worker — remove misleading `NotImplementedError` from default path when `TENANT_WORKER_MODULE` set |

### Acceptance criteria

- [ ] `git status` clean after `portal npm run build` (`.next` ignored)
- [ ] `./install-ai-stack.sh --mode enterprise` does not set global templateDir
- [ ] Release workflow validates tarball flat structure
- [ ] All 4.x cleanup items closed or explicitly wont-fix with comment

---

## Suggested merge order

| Order | PR | Rationale |
|-------|-----|-----------|
| 1 | **P0** | Unblocks production runtime story; portal DLQ becomes real |
| 2 | **P3** (partial) | Add redaction + portal `npm test` immediately after P0 stores land |
| 3 | **P1a + P1b** | Hooks + CD sync — low risk, high spec alignment |
| 4 | **P1c** | Shadow eval — can slip if Phoenix access is hard in CI |
| 5 | **P2** | Portal v2 — benefits from P1b sync + P0 run ingest |
| 6 | **P4** | CD scaffolding — tenant-facing, non-blocking |
| 7 | **P5** | Hygiene — anytime |

---

## Verification checklist (every PR)

From OPERATIONS.md §9:

```bash
find scripts runtime examples -name "*.py" -print0 | xargs -0 -n1 python3 -m py_compile
bash -n install-ai-stack.sh && zsh -n install-ai-stack.sh
cd portal && npx tsc --noEmit && npm test && npm run build
ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction
cd templates/in-app-widget && npm test
```

After P0, add:

```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test -p 55432:5432 postgres:16-alpine
export DATABASE_URL="postgresql://test:test@localhost:55432/test"
pytest runtime/test/ -q
docker rm -f pg-test
```

---

## Open questions (resolve before P1c / P4)

1. **Shadow eval Phoenix access in CI:** use team Phoenix secret or skip in self-test and run only on schedule?
2. **Widget CDN:** ship via GitHub Releases (`widget.js` asset) in P5.11, or defer until a domain exists?
3. **Rollback:** is Slack/Teams notification enough, or require a mandatory `ROLLBACK_COMMAND` secret in production environments?

---

*Previous Part 1–4 narrative archived above under **Resolved**. For architecture history see [docs/archive/specs-update.md](./docs/archive/specs-update.md) and OPERATIONS.md §12.*
