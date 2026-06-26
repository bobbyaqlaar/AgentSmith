# AgentSmith — Implementation PR Backlog

**Last reviewed:** 2026-06-22 (against OPERATIONS.md, SPECS.md, and full codebase)  
**Purpose:** Actionable implementation PRs for remaining gaps (P0–P5).

---

## ✅ Build complete (2026-06-23)

All four originally-deferred items (P1b, P1c, P2, P4) plus the P0.5
infra/design work are done and verified against the live Docker stack. The
full design history is at `/Users/mac/.claude/plans/fizzy-dazzling-teacup.md`
if you need file-level detail on any item below; this file is the
source of truth for *what's shipped*.

### Live infra — already running, do NOT recreate from scratch

```
agenticframework-db        Postgres 16, container, healthy   — 127.0.0.1:55432 (host, via docker-compose.override.yml — gitignored, local-only)
agenticframework-phoenix   Phoenix, container, healthy        — http://localhost:6006
agenticframework-portal    Ops Portal, container, healthy      — http://localhost:3000
```

Check with `docker compose ps` from the repo root. Credentials are in the
repo-root `.env` (gitignored — read it directly, don't ask, don't put its
contents in any tracked file). Two logical databases on
`agenticframework-db`: `phoenix` (Phoenix's own) and `agenticframework`
(Ops Portal + runtime data — tenants, audit_log, agent_runs, etc.).
**One real tenant already registered:** `acme`, `phoenixBaseUrl:
http://phoenix:6006` (internal docker hostname), with `budget_cap_usd:
250.5` synced from a throwaway `tenant.yaml` fixture (the fixture repo
itself, `/tmp/cap_test_repo`, may or may not still exist — irrelevant
either way, the sync already landed in the DB).

After pulling any new schema.sql changes: **rebuild before migrating** —
`docker compose build portal && docker compose run --rm portal npm run
db:migrate` (the image bakes in `schema.sql` at build time; running
migrate against a stale image silently no-ops new columns — this bit us
once already on `budget_cap_usd`, see P2b below).

### Status of the 4 deferred items + the infra/design work added on top

| Item | Status |
|---|---|
| P0.5a (containerize portal) | ✅ Done — `portal/Dockerfile`, `next.config.mjs` standalone output, `docker-compose.yml` `portal` service, `init-db/01-create-agenticframework-db.sh` |
| P0.5a-design (visual redesign) | ✅ Done — light/dark toggle (`components/ui/ThemeToggle.tsx`), `Card`/`Badge`/`MetricCard` in `components/ui/`, breadcrumb on tenant detail, new `/dlq` and `/audit` pages, restyled `CostChart`. Verified live in a real browser, both themes, all 4 pages. |
| P0.5b (vendor + machine-wide lifecycle) | ✅ Done — `install-ai-stack.sh` vendors `docker-compose.yml`+`init-db/`+`portal/` to `~/.agent-framework/observability/`; `ai-dashboard-start`/`-stop` redefined to manage the compose stack with a plain-process-Phoenix fallback. Tested against a scratch `$HOME`. |
| P0.5c (per-repo opt-out) | ✅ Done — `.agenticframework/no-shared-infra` marker, checked in `ai-dashboard-start` and `ai-tenant-init`'s output. Tested both branches. |
| P1b (CD → portal history sync) | ✅ Done — `scripts/sync-portal-history.py` (new), wired into `cd-staging.yml`/`cd-production.yml`/`ai-stack-check`, `verify_system.py --check-history-sync`. Verified live against the running portal (sync + idempotent re-sync + real CRITICAL issue surfaced via the API). |
| P2a (`agent_runs` + real run status) | ✅ Done — `agent_runs` table, `POST /api/runs/ingest`, `runtime/llm_gateway.py` emits running/success/degraded/failed via `_report_run_status`, `portal/lib/runStatus.ts` prefers it. **Also required a `middleware.ts` matcher fix** (had to add `api/runs/ingest` to the unauthenticated machine-to-machine exclusion list, same as `api/sync`). Verified live: a real `LLMGateway.complete()` call landed a `success` row, `GET /api/widget/status` reflected it. |
| P2b (cost cap from tenant.yaml) | ✅ Done — `tenants.budget_cap_usd` column (needed an explicit `ALTER TABLE ADD COLUMN IF NOT EXISTS` — `CREATE TABLE IF NOT EXISTS` alone is a no-op against the already-existing table, learned the hard way), `lib/tenants.ts`/`lib/cost.ts` updated, `/api/sync/history` accepts optional `budgetCapUsd` and **must preserve the tenant's existing `name`** on update (a real bug was caught and fixed: the update path was about to clobber `name` back to the raw `tenantId` on every cap sync — fixed by fetching `existingTenant.name` first), `scripts/sync-portal-history.py` reads `gateway.budget_cap_usd` from `tenant.yaml` via `pyyaml`. **Verified end to end:** `GET /api/tenants/acme/cost` returns `"cap":250.5`, and `GET /api/tenants` confirms `acme`'s `name` field is `"Acme"` (not clobbered to the raw `tenantId` by the fix above) — both checked against the live portal in the same session as the fix. |
| P2c (Phoenix GraphQL query depth) | ✅ Done — `portal/lib/phoenix.ts`'s `getRecentTraceStats()` queries the live Phoenix's `projects` + `Project.traceCountByStatusTimeSeries` (schema validated directly against the running `agenticframework-phoenix` container), rendered on the tenant detail page next to the Phoenix link (24h trace count + error-rate badge), degrades to omitted-line on any GraphQL failure. Verified live through the rebuilt portal container: `acme`'s page renders "Last 24h: 0 trace(s)" (real query executed, zero traces is correct — Phoenix's `default` project is empty). Unit test with mocked fetch (`portal/test/phoenix.test.ts`) added to `npm test` for CI regression coverage. `OPERATIONS.md` §F updated. |
| P1c (shadow eval sampler) | ✅ Done — `scripts/eval_judge.py` (new, judge-prompting/parsing logic factored out of `run-evals.py`'s `_judge_case`, which now delegates to it), `scripts/shadow-eval.py` (new, samples `environment=production` Phoenix spans deterministically by span_id hash, judges via the shared module, writes results back as `shadow_eval` span annotations tagged `eval.type: shadow` via Phoenix's REST `/v1/span_annotations`), `portal/lib/promotions.ts` (new, reads failing shadow annotations, degrades to `[]` on Phoenix errors), tenant detail page renders a "Suggested promotions" section, `workflow-templates/shadow-eval.yml` (new, opt-in nightly cron). **Verified live end-to-end**: pushed 6 real OTLP spans (one deliberately marked ERROR) into the running `agenticframework-phoenix` container, ran the sampler against them (with a mocked judge call only — no LLM API key in this dev environment; the Phoenix fetch/sample/annotate path is 100% real), confirmed annotations landed via direct REST query, confirmed idempotent re-run skips already-evaluated spans, rebuilt the portal container and confirmed the suggestions queue renders the real failures. CI regression: `scripts/test/test_shadow_eval.py` (sampling determinism/rate, judge-prompt shape) wired into `self-test.yml`'s `python-behaviour` job. |
| P4 (CD deploy/rollback automation) | ✅ Done — `.github/actions/deploy-placeholder/action.yml` (new, replaces the inline echo with a `DEPLOY_COMMAND`-secret-driven composite action) and `.github/actions/rollback-notify/action.yml` (new, Slack/Teams notify + optional `ROLLBACK_COMMAND` + fails the job) wired into both `cd-staging.yml` and `cd-production.yml`. **Verified live via `act`** (local GitHub Actions runner): ran both actions in a scratch workflow — placeholder no-ops with guidance when `deploy_command` is empty and runs the real command when set; rollback-notify prints rollback guidance when `rollback_command` is empty, runs it when set, and correctly fails the job (`exitcode '1'`) either way. `OPERATIONS.md` §D.5 "Wire your platform" added with Fly/Railway/ECS examples. |
| Final verification pass | ✅ Done — `find … -name "*.py" \| xargs py_compile`, `bash -n`/`zsh -n install-ai-stack.sh`, portal `tsc --noEmit && npm test && npm run build`, both `verify_system.py --check-redaction` profiles, widget `npm test`, `runtime/test/` + `scripts/test/` pytest against a throwaway Postgres, `verify_system.py --check-idempotency/--check-dlq/--check-hooks/--check-history-sync` (the last one against the live portal) — all green. **Found and fixed one real bug along the way**: `docker-compose.yml`'s `portal` healthcheck used `nc -z localhost 3000`, but the container's `/etc/hosts` resolves `localhost` to `::1` first while Next's standalone server only binds `0.0.0.0` (IPv4) — the healthcheck was failing (`unhealthy`, 35-deep failing streak) even though the portal worked correctly the whole time (confirmed via direct `curl`). Changed to `127.0.0.1`; rebuilt, now reports `healthy`. |

### Documents updated this session that are already current (no ambiguity)

`OPERATIONS.md`, `SPECS.md`, `Readme.md`/`README.md` (same file, case-
insensitive filesystem), and `UserManual.md` were all updated earlier in
this session and are accurate as of now — no further doc reconciliation
needed before continuing the remaining build items above. The plan file
is the single source of truth for *what's left*; this backlog file is the
source of truth for *what's already shipped*.

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

## Completed — second implementation pass (2026-06-23)

| ID | Topic | Resolution |
|----|-------|------------|
| P0 | Idempotency store | `runtime/idempotency.py` `_RedisBackend`/`_PostgresBackend` implemented for real; `llm_gateway.py` logs (not silently swallows) lookup/write failures |
| P0 | Dead-letter queue | `runtime/dead_letter.py` Postgres-backed `enqueue`/`list`/`replay`/`discard`; `replay()` takes an optional `replay_handler` callback (workflow-engine-specific re-enqueueing is pluggable, not hardcoded) |
| P0 | DLQ activity wiring | `examples/oil-price-agent/workflows/activities.py`'s `dead_letter_activity` no longer swallows `NotImplementedError` — the backend is real now |
| P0 | Idempotency key emission | `run_prediction_activity` now passes `idempotency_key=make_key(...)` keyed on workflow_run_id + activity name + actual input, so a Temporal retry of the same call dedupes without colliding with other activities/inputs |
| P0 | CI checks | `scripts/verify_system.py --check-idempotency` / `--check-dlq`, run against a throwaway Postgres in `self-test.yml`'s new `python-behaviour` job |
| P1a | Hook opt-in gate | `hooks/pre-commit`/`commit-msg`/`post-commit` no-op unless `.agenticframework/enabled`, `tenant.yaml`, or an org policy file exists; `hooks/post-checkout` writes the `enabled` marker on first provision (kept unconditional — it's the bootstrap step) |
| P1a | Enterprise RFC gate | `pre-commit` requires ≥1 RFC under `.agent-rfc/` when org policy present; `commit-msg` requires an `RFC-NNN` reference in the message itself (split this way because pre-commit has no access to the commit message) |
| P1a | CI check | `scripts/verify_system.py --check-hooks` simulates both opt-in and enterprise-RFC scenarios in throwaway git repos |
| P3 | Portal behavior tests in CI | `self-test.yml`'s `portal` job now runs `npm test` (cross-tenant isolation) and `npm run test:db` (new `portal/test/auditLog.test.ts` — HMAC sign/verify, tamper detection, append-only trigger enforcement) against a real Postgres service |
| P3 | Runtime behavior tests | `runtime/test/test_llm_gateway_budget.py` (concurrency, reservation release/reconciliation, free-tier bypass) and `test_trace_redactor.py` (redaction profiles, per-span tenant binding, blob-ref collision, missing-key logging, `get_environment()` fail-closed) — both run via `pytest`, added to `requirements.txt` |
| 5.2 | `install-ai-stack.sh --mode` | `developer` (default) / `enterprise` flag; enterprise mode skips the global `git config --global init.templateDir` mutation |
| 5.10 | `<org>` placeholder | Replaced with `YOUR_ORG` + an overridable `AI_STACK_FRAMEWORK_REPO` env var (the literal `<org>` was actually used in URL construction, not just doc prose — it would have broken release-download fallback paths) |
| 5.11 | Widget CDN | `cdn.agenticframework.io` was never a real hosted domain — docs now point at self-hosting, and `release.yml` ships `widget.js` as a downloadable release asset |
| 5.12 | `runtime/worker.py` | `TENANT_WORKER_MODULE` env var: dispatches to a tenant-supplied module's `start_temporal_worker`/`start_celery_worker(tenant_id)` if set; unchanged (raises with guidance) if not — copying the file's shape into a tenant repo (`examples/oil-price-agent/worker.py`) remains the other supported path |

All of the above were verified against live infra before being marked done — a throwaway Postgres (docker), a Python venv with `psycopg2`/`redis`/`pytest`/`opentelemetry-sdk`, and the portal's actual `npm test`/`npm run build`/`tsc --noEmit` — not just read-through review. (P1b/P1c/P2/P4 were deferred out of this particular pass for needing a live Ops Portal/Phoenix instance to validate meaningfully — all four were implemented and verified live in later sessions; see their own rows above and P6/P7 below, not duplicated here.)

## Verification note (2026-06-23)

Every claim in this file was checked directly against the codebase before
acting on it. Two corrections from the prior draft:

- **P5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9 were already implemented** in the
  second fix pass (mapped 4.9, 4.11, 4.7/4.8, 4.6, 4.4, —, 4.13
  respectively) and are removed from the P5 scope table below — re-checked
  directly in `install-ai-stack.sh`, `hooks/post-commit`,
  `portal/app/api/tenants/route.ts`, `scripts/cost_router.py`,
  `runtime/k8s/dedicated-tenant/configmap.yaml`, and
  `.github/workflows/release.yml`. Only 5.1 (already marked Done), 5.2,
  5.10, 5.11, 5.12 remain open.
- **P3's problem statement overstated the gap.** `self-test.yml`'s
  `widget` job already runs `npm test` — the real XSS-regression behavioral
  suite, not just parse/build. The actual gap is narrower: the `portal` job
  runs `tsc --noEmit && npm run build` but never `npm test` (so
  `authz.test.ts` isn't in CI), and there's no Postgres-backed job for
  `runtime/` Python tests at all.
- **P0's "pin redis if not present" was already moot** — `redis>=5.0,<6.0`
  is already in `requirements.txt`.

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

## P0 — Production runtime: idempotency, DLQ, worker wiring ✅ done

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

### Acceptance criteria

- [x] `IDEMPOTENCY_BACKEND=postgres` + `DATABASE_URL`: second `complete()` with same key returns cached result without provider call (verified against a real throwaway Postgres)
- [x] `DeadLetterQueue.enqueue()` persists row; `GET /api/dlq`'s exact query (`portal/lib/dlq.ts`) returns the row, verified directly against Postgres
- [x] `replay(task_id)` marks replayed with an audit-trail-style log entry by default; re-enqueues via an optional `replay_handler` callback for true Temporal/Celery automation (engine-specific, intentionally pluggable rather than hardcoded to one engine)
- [x] OPERATIONS.md §D.4 "Known gap" paragraph replaced with setup instructions
- [x] `docker run postgres:16` + pytest (`runtime/test/test_llm_gateway_budget.py`, `test_trace_redactor.py`) passes — wired into `self-test.yml`'s new `python-behaviour` job (see P3)

### Docs

- OPERATIONS.md §D.1–D.4, SPECS.md §25 TODOs

---

## P1 — Spec/code alignment: hooks, CD sync, shadow evals

**Branch:** `feat/spec-alignment-hooks-cd-shadow`  
**Depends on:** none (orthogonal to P0; merge order flexible)
**Status:** P1a done (this pass). P1b/P1c deliberately deferred — see "Completed — second implementation pass" above for why.

### Problem

Several SPECS/OPERATIONS claims are not enforced in code: developer opt-in hooks, enterprise RFC pre-commit, automatic history sync in CD workflows, and shadow evals (SPECS.md §9) have no implementation.

---

### P1a — Developer opt-in + enterprise RFC hooks ✅ done

| File | Change |
|------|--------|
| `hooks/pre-commit` | If org policy absent: require `.agenticframework/enabled` or `.agenticframework/tenant.yaml` or exit 0 (skip). If org policy present: require ≥1 RFC under `.agent-rfc/*.md` |
| `hooks/commit-msg` | Same opt-in gate; if org policy present, require `RFC-NNN` in the commit message itself (this hook — not pre-commit — actually receives the message; see note below) |
| `hooks/post-commit` | Same opt-in gate at top (after `DISABLE_AI_STACK`) |
| `hooks/post-checkout` | **Not gated** (deliberate deviation) — this hook is the bootstrap step that PROVISIONS `.agenticframework/enabled` in the first place; gating it the same way would mean a brand-new `git init` never gets provisioned at all. It writes the `enabled` marker at the end of a successful provision instead. |
| `scripts/verify_system.py` | `--check-hooks` simulates opt-in / RFC block in throwaway git repos |

**Note on the RFC split:** the original ask was "pre-commit: require RFC-NNN in commit message" — but pre-commit runs before the commit message exists/is accessible to it (git hook ordering). The precise per-commit RFC-NNN check lives in `commit-msg` instead (which does receive the message); `pre-commit` only enforces the coarser "this repo has ≥1 open RFC at all."

**Acceptance criteria**

- [x] Repo without `.agenticframework/enabled` and without org policy: hooks no-op
- [x] Repo with `enabled` + org policy: commit without RFC reference blocked in enterprise mode
- [ ] SPECS.md §7 install modes match installer behaviour — not re-verified in this pass

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

## P3 — CI behaviour tests (self-test expansion) ✅ done

**Branch:** `feat/self-test-behaviour`  
**Depends on:** P0 for gateway/store tests; portal tests independent

### Problem

`.github/workflows/self-test.yml`'s `widget` job already runs `npm test`
(the real XSS-regression behavioral suite) — but the `portal` job only runs
`tsc --noEmit && npm run build`, never `npm test`, so `authz.test.ts` (the
cross-tenant isolation suite) doesn't run in CI. There's also no
Postgres-backed job for `runtime/` Python behavioral tests, and no
redaction-profile check wired in at all.

### Scope

| File | Change |
|------|--------|
| `.github/workflows/self-test.yml` | Add jobs: `portal npm test`, `ENVIRONMENT=staging|production verify_system --check-redaction`, Postgres service + `runtime/test/` |
| `runtime/test/test_llm_gateway_budget.py` | **New.** Concurrent `try_reserve` cannot exceed cap |
| `runtime/test/test_trace_redactor.py` | **New.** API keys redacted in staging/production profiles |
| `portal/test/auditLog.test.ts` | **New.** HMAC sign/verify round-trip |
| `requirements.txt` | Add `pytest` explicitly |

### Acceptance criteria

- [x] PR to `main` runs all new jobs green — verified locally (Postgres service equivalent run via docker, all green)
- [x] Regression in RBAC (`authz.test.ts`) fails CI — suite runs via `npm test` in `self-test.yml`'s `portal` job
- [x] Redaction regression fails CI — `ENVIRONMENT=staging/production --check-redaction` wired into the `python` job

---

## P4 — CD/deploy templates and rollback scaffolding ✅ done

**Branch:** `feat/cd-deploy-scaffolding`  
**Depends on:** none

### Problem (resolved)

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
- [x] Production smoke failure fails the workflow **and** runs rollback-notify action — verified via `act` (forced failure propagates exit 1 after rollback/notify steps run)
- [x] Tenant can set `DEPLOY_COMMAND` secret without editing workflow YAML — `deploy-placeholder` action reads `secrets.DEPLOY_COMMAND`, verified via `act` with and without it set

---

## P5 — Repo hygiene and remaining cleanup

**Status: all items done** — see "Completed — second implementation pass" above.

| ID | File | Change |
|----|------|--------|
| ~~5.1~~ | ~~`.gitignore`~~ | **Done** — root ignore file added (+ `.pytest_cache/` added in this pass) |
| ~~5.2~~ | ~~`install-ai-stack.sh`~~ | **Done** — `--mode developer\|enterprise` |
| ~~5.3~~ | ~~`install-ai-stack.sh`~~ | **Done** — `ai-stack-upgrade` already checks `git commit` exit code (4.9) |
| ~~5.4~~ | ~~`install-ai-stack.sh`~~ | **Done** — `ai-stack-scrub` already lists exact paths before confirm prompt (4.11) |
| ~~5.5~~ | ~~`hooks/post-commit`~~ | **Done** — except already narrowed (4.7); heredoc already quoted (4.8) |
| ~~5.6~~ | ~~`portal/app/api/tenants/route.ts`~~ | **Done** — `upsertTenant` already a static import (4.6) |
| ~~5.7~~ | ~~`scripts/cost_router.py`~~ | **Done** — `_consecutive_failures` already bounded (4.4) |
| ~~5.8~~ | ~~`runtime/k8s/dedicated-tenant/configmap.yaml`~~ | **Done** — accepted values already commented |
| ~~5.9~~ | ~~`.github/workflows/release.yml`~~ | **Done** — tarball extract + structure check already present (4.13) |
| ~~5.10~~ | ~~`Readme.md`, `install-ai-stack.sh`, `UserManual.md`~~ | **Done** — `YOUR_ORG` + `AI_STACK_FRAMEWORK_REPO` |
| ~~5.11~~ | ~~`templates/in-app-widget/`~~ | **Done** — `widget.js` shipped as a release asset; docs point at self-hosting |
| ~~5.12~~ | ~~`runtime/worker.py`~~ | **Done** — `TENANT_WORKER_MODULE` dispatch |

### Acceptance criteria

- [x] `git status` clean after `portal npm run build` (`.next` ignored)
- [x] `./install-ai-stack.sh --mode enterprise` does not set global templateDir
- [x] Release workflow validates tarball flat structure
- [x] All 4.x cleanup items closed or explicitly wont-fix with comment

---

## P6 — CI/CD industry-parity + on-prem/air-gapped deployment (2026-06-23) ✅ done

Raised by comparing this framework's CI/CD against a 3-phase
CI/standard-evaluation/CD model an external review proposed. Two real
gaps closed; the third (canary/shadow strategy) was deliberately expanded
beyond the original ask once on-prem/air-gapped requirements came in —
see OPERATIONS.md D.6.

| Item | Change |
|---|---|
| Formatter gate (Python CI) | `ruff format --check .` added to `workflow-templates/ci-python-fastapi.yml` (TS/Go already had lint/`gofmt` gates) |
| Containerize + push to GHCR | New `.github/actions/build-push-ghcr/` composite action — builds + pushes `ghcr.io/<org>/<repo>:<sha>` using the workflow's own `GITHUB_TOKEN`, skips cleanly (no CD failure) if no `Dockerfile` exists. Wired into `cd-staging.yml`/`cd-production.yml` before the deploy step; exports `$IMAGE_REF` for `DEPLOY_COMMAND`/the on-prem template to consume. |
| On-prem/air-gapped canary + shadow traffic | **New** `templates/onprem-deploy/` — stack-agnostic (single image + `/healthz` + env-only config + stdout JSON logs contract), opt-in via new `ai-onprem-deploy-scaffold` shell function (vendored like `agent-rules.yaml`, never auto-written by `ai-tenant-init`). Docker Compose path with a customer choice of Traefik or Envoy (both real, schema-validated configs rendered from `.env` via `scripts/render-{traefik,envoy}-config.py`); Kubernetes/Helm path (`templates/onprem-deploy/kubernetes/`) using the **core** Gateway API (`backendRefs[].weight` for canary, `RequestMirror` filter for shadow — portable across Traefik's and Envoy Gateway's Gateway API implementations) for high-compliance enterprises who won't run raw Docker. Air-gapped bundling via `docker save`/`docker load` scripts. |
| Verification | `scripts/verify_system.py --check-onprem-deploy` (renders both proxy engines + validates `docker compose config` for 3 profile combinations + `helm lint`/`helm template` across 3 value combinations) — wired into `self-test.yml`'s `python` job. Live-tested end-to-end: full `install-ai-stack.sh` run against a scratch `$HOME`, sourced the resulting shell-rc block, ran `ai-onprem-deploy-scaffold` in a scratch tenant repo, confirmed `deploy/onprem/` lands correctly. |

**Known limitation, documented not hidden:** core Kubernetes Gateway API's
`RequestMirror` filter has no percentage field (always mirrors 100% of
matched traffic) — Traefik's/Envoy's own native proxy mirroring used
directly in the Compose path does support a percent. Partial-percentage
shadow mirroring specifically on K8s requires a vendor extension (Istio's
`VirtualService.httpMirrorPercentage`, Envoy Gateway's
`BackendTrafficPolicy`) intentionally left out to keep the chart portable
across both supported proxy engines using only the open Gateway API
standard — see `templates/onprem-deploy/kubernetes/README.md`.

---

## P7 — Code-review fixes + HITL/DLQ redesign (2026-06-23/24) ✅ done

### Code-review fixes (ultra pass on this session's uncommitted changes)

Three confirmed regressions/bugs caught by a 5-finder-angle review +
manual live verification, fixed in place (not just reported):

| Bug | Fix | Verified |
|---|---|---|
| `cd-production.yml`'s new `permissions: {contents: read}` block (added for the GHCR step above) silently broke the pre-existing "Open PR for fixture updates" step, which needs to push a branch + open a PR with the same `GITHUB_TOKEN` | `contents: write` + `pull-requests: write` | YAML parses; reasoning verified against the step's actual `git push`/`gh pr create` calls |
| `templates/onprem-deploy/scripts/up.sh`: `"${PROFILE_ARGS[@]}"` on an empty array throws "unbound variable" under `set -u` on bash <4.4 (macOS's stock `/bin/bash`, still 3.2) — hits the default prod-only case every time | `${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}` | Reproduced the failure on bash 3.2, confirmed the fix handles both empty and non-empty cases |
| `templates/onprem-deploy/kubernetes/templates/db-statefulset.yaml` renders `secretRef.name: ` (empty) when `withDb.enabled=true` but `credentialsSecretName` is unset — invalid K8s manifest | Wrapped in Helm's `required` function — fails fast with a clear message instead | `helm template` confirmed: fails loudly without the value, succeeds with it |

Three additional findings were implemented as the deeper fix the reviewer
recommended, not just patched:

| Finding | Fix |
|---|---|
| `llm_gateway.py`'s `run_id` was reused across every `complete()` call within one `workflow_id` — a 2nd call's "running" report would re-upsert a 1st call's already-"success" `agent_runs` row, resetting `finished_at` to NULL | `run_id` is now unique per call; `workflow_id` is now actually transmitted to `/api/runs/ingest` (was silently dropped before — every row had `workflow_id=NULL` regardless of what the caller passed); `portal/lib/runStatus.ts` aggregates a workflow's calls into one status ("running" if any open — covers sequential AND concurrent fan-out — else worst terminal status) |
| `render-{traefik,envoy}-config.py` accepted out-of-range `CANARY_WEIGHT_PERCENT`/`SHADOW_MIRROR_PERCENT` (negative, >100), producing a technically-valid-looking but semantically-broken proxy config | Both scripts now validate 0-100 and exit 1 with a clear message before rendering anything |
| `dead_letter_activity` (oil-price example) generated a fresh UUID per call — a Temporal retry of the activity itself (before it returns successfully) would create duplicate DLQ rows for one logical failure | `DeadLetterQueue.enqueue()` is now idempotent on `task_id` (`ON CONFLICT DO NOTHING`, protects every caller); the activity also derives a stable `task_id` from `workflow_run_id` |

All six verified live: real throwaway Postgres for the DLQ/idempotency
fixes, a real `temporalio.testing.WorkflowEnvironment` run for the
run_id/workflow_id aggregation fix (see below — same infrastructure), the
real running Ops Portal container for the `runStatus.ts` aggregation.

### HITL/DLQ redesign

Raised by an external review of "agent failure → human dashboard → fix →
replay seamlessly" patterns (Slack+Retool, LangGraph interrupts, Temporal
durable execution). Temporal durable execution was the right fit — the
framework already had the primitive (`workflow.wait_condition` + a
signal), it just needed generalizing. Closes 5 gaps in the prior HITL/DLQ
implementation:

| Gap (prior implementation) | Fix |
|---|---|
| "Replay" didn't actually replay anything — the workflow that timed out had already terminated, nothing left to resume | **New** `run_with_recoverable_step` (`runtime/workflows/base_workflow.py`) — on activity failure, the workflow stays **alive**, parks on a per-gate signal instead of terminating. **New** `runtime/temporal_replay.py`'s `make_temporal_replay_handler(client)` signals that live workflow for real. |
| No structured failure reason — DLQ's `error` was free text only | `dlq_entries.reason` (`validation_error`/`tool_call_error`/`hitl_timeout`/`hitl_rejected`/`infra_error`) |
| Hardcoded 24h timeout, no per-tenant/per-gate lever | `run_with_recoverable_step(..., timeout=...)` is now a caller-supplied parameter |
| One global boolean signal — no way to know which gate a signal answers if a workflow has multiple HITL gates | `gate_id` keys both the DLQ entry and the `human_fix_payload` signal (`Dict[str, Any]`, not a single field) |
| No notification on timeout — a human had to happen to check `/dlq` | `DeadLetterQueue.enqueue()` posts to `SLACK_WEBHOOK_URL`/`TEAMS_WEBHOOK_URL` on every new entry |

Plus the editable-payload UX (the CRM example: agent hallucinates
`{"account_status": "active"}`, schema expects `"status"`, operator
edits the JSON and clicks Replay):

- `dlq_entries` gains `reason`/`workflow_id`/`gate_id` (migrated via
  `ALTER TABLE ADD COLUMN IF NOT EXISTS` inside `dead_letter.py`'s own
  `__init__` — that table is Python-owned, not part of
  `portal/db/schema.sql`).
- `DeadLetterQueue.replay(task_id, override_payload=...)` — the override
  is what actually gets signaled and persisted, not the original failing
  payload.
- **The portal-to-worker bridge is a per-tenant webhook, not a direct
  Temporal connection** (deliberate choice — the portal stays engine-
  agnostic, a tenant could run Celery instead): `tenants.replay_webhook_url`/
  `replay_webhook_secret` (synced from `.agenticframework/tenant.yaml`'s
  `hitl.*` section, same mechanism as `budget_cap_usd` —
  `scripts/sync-portal-history.py` extended accordingly), deliberately
  per-tenant so a fix always reaches the team running that tenant's
  worker, never a shared cross-tenant endpoint. `replay_webhook_secret`
  is the one DB-stored value never exposed via any API response —
  `portal/lib/tenants.ts`'s public `Tenant` type carries the URL only;
  `getReplayWebhookConfig()` is a separate, deliberately narrow accessor.
- **New** `runtime/replay_webhook_server.py` — reference stdlib
  `http.server` receiver, HMAC-verifies the portal's signed payload, then
  calls `DeadLetterQueue(replay_handler=...).replay(task_id, override_payload=...)`.
- Ops Portal: `/dlq/<tenantId>` per-tenant entry list (editable JSON
  textarea, Replay/Discard buttons — `DlqEntryCard.tsx`), replacing the
  prior aggregate-pending-count-only view. `POST /api/dlq/:taskId/replay`
  always derives `tenantId` from the entry's own DB row, never trusts a
  client-supplied one (would otherwise let a client redirect a replay to
  a different tenant's webhook). Discard is a direct DB write (safe — it
  never needs to resume a live workflow); replay always round-trips
  through the webhook.

**A real bug was caught and fixed by live testing, not assumed away:**
without `retry_policy=RetryPolicy(maximum_attempts=1)` on the gated
`execute_activity` call, Temporal's *default* retry policy retries the
same failing payload indefinitely (with backoff) until
`start_to_close_timeout` — the recoverable-step logic wouldn't even
engage for up to 10 minutes. Caught via a real
`temporalio.testing.WorkflowEnvironment` run that hung; fixed, then
re-verified the exact CRM example end-to-end (workflow fails once, parks,
`human_fix_payload` signal resumes it, activity succeeds with the
corrected payload) — `Completing activity as failed` appeared exactly
once in the worker log, not in a retry storm.

**Verified live, not unit-tested in isolation:**
- `dead_letter.py`'s idempotent enqueue + `override_payload` replay —
  real throwaway Postgres, exact CRM payload.
- `run_with_recoverable_step` — real Temporal test server
  (`temporalio.testing.WorkflowEnvironment`), real worker, real signal.
- `replay_webhook_server.py`'s HMAC verification — real signed/unsigned/
  wrong-path requests.
- The full portal-to-webhook bridge — real running Ops Portal container +
  a stub HMAC-verifying receiver: `POST /api/dlq/:taskId/replay` with an
  edited payload produced a correctly-signed call with the edited JSON
  intact; 401 unauthenticated, 404 unknown/out-of-scope task, 409
  already-resolved all confirmed.
- `scripts/sync-portal-history.py`'s new `hitl.replay_webhook_url`/
  `secret` sync path — real fixture `tenant.yaml`, real running portal,
  confirmed the values land in `tenants.replay_webhook_url`/`_secret`.

---

## Suggested merge order

| Order | PR | Rationale | Status |
|-------|-----|-----------|--------|
| 1 | **P0** | Unblocks production runtime story; portal DLQ becomes real | ✅ done |
| 2 | **P3** | Add redaction + portal `npm test` immediately after P0 stores land | ✅ done |
| 3 | **P1a + P1b** | Hooks + CD sync — low risk, high spec alignment | ✅ done |
| 4 | **P1c** | Shadow eval — can slip if Phoenix access is hard in CI | ✅ done |
| 5 | **P2** | Portal v2 — benefits from P1b sync + P0 run ingest | ✅ done |
| 6 | **P4** | CD scaffolding — tenant-facing, non-blocking | ✅ done |
| 7 | **P5** | Hygiene — anytime | ✅ done |

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

## P9 — Redundancy/staleness cleanup (2026-06-25) ✅ done

Found by a full-repo (not diff-scoped) review specifically hunting for
duplicate/dead code and stale docs, not bugs. Four items acted on; three
deliberately left open pending further discussion (recorded so they aren't
re-surfaced as "forgotten" — see the review conversation for the deferred
items' pros/cons: a 3-way duplicated Caddy/TLS setup across
`docker-compose.yml`/`OPERATIONS.md`/`docs/team-observability.md`, whether
`openinference-instrumentation-*` should be wired up or dropped, and
whether `prophet`/`pandas`/`numpy` should be removed now or kept for the
oil-price example's still-TODO real forecasting model).

| Item | Change |
|---|---|
| Duplicate helpers across `scripts/*.py` | **New** `scripts/_shared.py` — `_repo_root()` (was byte-identical in 10 files), `_iso_now()` (4 files), `_tenant_id()` (2 files, consolidated on the more robust YAML-parse-first version), `_phoenix_get`/`_phoenix_post` (2 files, consolidated on the RuntimeError-wrapping version). Deliberately NOT shared with `runtime/llm_gateway.py`'s own separate copy of `_repo_root()` — `runtime/` is vendored independently of `scripts/`, sharing would couple two things meant to stay independently deployable. |
| `tenacity` required by `verify_system.py`'s health check but never imported anywhere | `runtime/llm_gateway.py`'s `_invoke()` now retries `httpx.TransportError`/429/5xx with exponential backoff (`stop_after_attempt(3)`, `wait_exponential`) — this is the "Throttle: exponential backoff on request rate" degrade-ladder step the module's own docstring has described since it was written, just never implemented. Non-retryable errors (401, 400, etc.) still fail on the first attempt. Verified live: a mocked 503-twice-then-200 sequence retries and succeeds on attempt 3; a mocked 401 fails on attempt 1 with zero retries. Regression tests added to `runtime/test/test_llm_gateway_budget.py`. |
| `examples/oil-price-agent`'s `OilPricePredictionWorkflow` reimplemented `BaseAgentWorkflow`'s signal pattern inline instead of subclassing it | Now actually `class OilPricePredictionWorkflow(BaseAgentWorkflow)` — inherits `hitl_approved`/`self._hitl_approved` rather than redefining them. The order-placement step (`decide_action_activity`) is now wrapped in `run_with_recoverable_step` (previously a bare `execute_activity`) and validates its payload shape, demonstrating the CRM-style edit-and-replay pattern in the framework's own reference example for the first time. Required moving the `sys.path.insert(..., Path(...).resolve()...)` calls needed to import `base_workflow` out of `oil_price_workflow.py` itself and into `worker.py` — Temporal's sandbox re-imports whatever module defines a workflow class for determinism validation, and a `Path.resolve()` call at that module's top level trips the sandbox's restriction on it (a real `RuntimeError: Failed validating workflow` caught by actually running this against a Temporal test server, not assumed). Verified live end-to-end: a real `WorkflowEnvironment` run where `decide_action_activity` fails once (simulated hallucinated field), parks alive, and resumes correctly via a `human_fix_payload` signal with the corrected payload. |
| `docs/archive/specs-update.md` (940 lines, zero functional inbound links, already marked superseded at its own top line) | Deleted, along with the now-empty `docs/archive/` directory. Two stale references fixed: `FIXES_AND_CLEANUP.md`'s footer link (was pointing at the deleted file) and `SPECS.md`'s repo-tree listing (still showed the `archive/` directory). |

---

## Future Phases — confirmed gaps, not yet scheduled

Surfaced by a deliberate audit against a functional/non-functional layer
checklist (Readme.md/SPECS.md's "Architecture by Layer" sections), not by
a bug report — these are honest absences, not regressions. Each is listed
with a **trigger condition** (the concrete signal that means "build this
now," not a calendar date) and **rationale**, so a future session can
decide whether the trigger has actually fired instead of re-litigating
whether the gap matters. Two design decisions were already made for items
below (recorded so they aren't re-opened): MCP integration stays
tenant-owned (BYO), not shipped by the framework; the LLM self-correction
loop, if built, is a separate opt-in method, not inserted in front of the
existing human DLQ escalation path.

### Memory Management — short-term (token-window) + long-term (vector store)

**Gap:** no token-window truncation/summarization/sliding-window manager,
no vector-database integration (Chroma/pgvector/etc.) anywhere in the repo.

**Trigger:** the first tenant app that needs either (a) a conversation
longer than fits in one context window, or (b) semantic retrieval over a
corpus too large to put in a prompt directly. Building either
speculatively, before a real call site needs it, risks guessing the wrong
shape (e.g. summarization vs. sliding-window truncation depend heavily on
the actual conversation pattern of the app that needs it).

**Fix sketch, when triggered:**
- Short-term: a `runtime/conversation_memory.py` module wrapping a message
  list with a configurable token budget (via `tiktoken`, already a
  dependency) and a pluggable eviction strategy (truncate-oldest first;
  summarization via a `gw.complete()` call is a reasonable v2, not v1).
- Long-term: a thin `runtime/vector_store.py` interface (`add`, `query`)
  with a Postgres+pgvector backend as the default implementation —
  consistent with this framework's existing bias toward Postgres-backed
  state (idempotency, DLQ, budget) over adding a new infra dependency
  class. Chroma/Pinecone become alternate backends behind the same
  interface only if a concrete tenant need for one of them shows up.

### Tool Orchestration — registration/schema-extraction, MCP

**Gap:** no `@tool`-style decorator extracting a Python function's
signature into a JSON schema; `llm_gateway.py.complete()` has no
function-calling fields in the provider request at all — it sends a
prompt, gets text back.

**Decision (settled, do not re-open without a concrete reason):** MCP
integration stays **bring-your-own** — the framework does not ship an MCP
client/server. Rationale: AgentSmith's stated design goal is
supporting tenant apps of "any architecture or languages," and MCP is one
tool-orchestration standard among several a tenant might already use;
shipping it as first-class would tie every tenant to that standard and
commit this framework to tracking MCP's spec evolution, for a capability
that's orthogonal to what this framework actually owns (budget/redaction/
tracing/HITL around an LLM call, not the orchestration logic in front of
it).

**Trigger:** if a tool-schema/registration layer is still wanted despite
the above (independent of MCP specifically) — the trigger is a tenant
reference app (e.g. a successor to `examples/oil-price-agent`) whose
domain genuinely needs the LLM to choose among several tools dynamically,
as opposed to the current examples' fixed activity sequences.

**Fix sketch, when triggered:** a small `runtime/tool_registry.py` with a
decorator that introspects type hints/docstrings into a JSON schema,
independent of any specific orchestration protocol — a tenant's own MCP
client (or direct function-calling against a provider's API) consumes the
schema however it needs to; this framework doesn't pick the protocol.

### Perception & Input Parsing — structured output parsing, prompt templating

**Gap:** the reference pipelines (`multi_agent_system.py`,
`local_agent_stack.py`) extract JSON from LLM text via bare
`re.search`+`json.loads()` with a hardcoded fallback shape — no schema
validation. No reusable prompt-template engine exists; prompts are inline
f-strings built once per call site.

**Trigger:** a second reference pipeline (or a real tenant app) that
duplicates either the JSON-extraction pattern or a near-identical prompt
structure — i.e., once there are 2+ real call sites with the same shape,
not before. Building an abstraction for a single call site is the kind of
premature generalization this framework's own contributor conventions
warn against.

**Fix sketch, when triggered:** `runtime/structured_output.py` (Pydantic
model + `model_validate_json`, raising a typed error on mismatch instead
of falling back to a hardcoded `{"verdict": "FAIL"}`-style shape) and
`runtime/prompt_templates.py` (a minimal Jinja2 or `string.Template`
wrapper — no need for a heavier templating dependency than the job needs).

### Human-in-the-Loop — LLM-driven self-correction

**Gap:** every recovery path that exists today is human-driven (DLQ
edit-and-replay) or Temporal-driven (transient-failure retry) — there is
no path where the model sees its own tool-call error and retries with a
corrected call before any human is involved.

**Decision (settled):** if built, this is a **separate, opt-in method**
(e.g. `run_with_self_correction`), not inserted in front of
`run_with_recoverable_step`'s existing human-escalation path. Rationale:
keeps the already-shipped, already-tested human-escalation behavior
completely unchanged for every existing call site; a tenant who wants
model-driven retry for a specific failure class opts into the new method
at that call site deliberately, rather than every recoverable-step call
silently gaining a new (and initially less battle-tested) retry behavior
in front of it.

**Trigger:** a tenant reports DLQ volume dominated by an error class a
model could plausibly self-correct on the first retry (e.g. a field-name
mismatch like the CRM example) — i.e., evidence from real DLQ `reason`
distribution, not a guess that this would help.

**Fix sketch, when triggered:** `run_with_self_correction(activity_name,
payload, tenant_id, max_self_correction_attempts, ...)` — on activity
failure, calls `gw.complete()` with the original payload + the error
message, asks the model for a corrected payload (via the structured-output
parser above, once it exists), retries up to
`max_self_correction_attempts`, and only then falls through to enqueuing
a DLQ entry exactly as `run_with_recoverable_step` does today — reusing
that DLQ-enqueue path rather than duplicating it.

### Security & Guardrails — pre-call input sanitization

**Gap:** `trace_redactor.py` redacts/anonymizes data **after** a call, for
what gets written to Phoenix/logs. There is no symmetric **pre-call**
guardrail — nothing scrubs PII or moderates content in the prompt actually
sent to the model.

**Trigger:** a tenant app that accepts untrusted end-user input directly
into a prompt (as opposed to the current examples, which only take
structured internal data — price series, payloads — never free-text user
input). Pre-call guardrails matter most exactly where prompt injection and
unintended PII-to-model exposure are real risks, which requires an actual
untrusted-input call site to design against correctly.

**Fix sketch, when triggered:** a `runtime/input_guardrail.py` hook point
in `llm_gateway.py.complete()`, called before `_invoke()` — pluggable
(framework provides the call site, not a specific moderation model),
matching the framework's existing pattern of providing the mechanism and
letting the tenant supply the policy (same shape as `replay_handler`,
`TENANT_WORKER_MODULE`).

### Reliability & Accuracy — hallucination-rate metric

**Gap:** `run-evals.py`/`eval_judge.py` score `correctness`,
`tool_accuracy`, `latency` — no metric is literally named "hallucination
rate"; a hallucination today just shows up as a low `correctness` score.

**Trigger:** a tenant or stakeholder needs hallucination tracked as its
own reportable number (e.g. for a compliance requirement stating "< 5%
hallucination incidents" specifically, not "correctness ≥ some
threshold") — the two are not the same number and conflating them would
misrepresent whichever one is actually being asked for.

**Fix sketch, when triggered:** add a `hallucination` field to the judge's
scored output in `.agent-rfc/fixtures/custom_judge_criteria.json` (a new
judge-prompt dimension asking specifically "did the response state
something not supported by the input/retrieved context," distinct from
"was the response correct") — additive to the existing scorecard, not a
replacement for `correctness`.

### Scalability & Performance — Time-to-First-Token

**Gap:** `llm_gateway.py` makes one non-streaming HTTP call per
`complete()` — there is no first-token timestamp anywhere, so TTFT cannot
be measured, only total call latency.

**Trigger:** a tenant app with a user-facing "streaming response" UI
(e.g. a chat interface showing tokens as they arrive) — TTFT only matters
as a UX metric once there's a UI that actually benefits from streaming;
without one, total latency is the only number that affects anything.

**Fix sketch, when triggered:** add a streaming code path to
`runtime/provider_dispatch.py` (provider SDKs already support
streaming — this is wiring, not new capability), record the first-chunk
timestamp in `_invoke()`, add `ttft_ms` alongside the existing
`cost_usd`/token counts in `_record_span_attributes`. Non-streaming
`complete()` stays the default — streaming is an opt-in mode, since most
of this framework's existing call sites (batch predictions, decision
agents) have no UI to stream to.

### Data Bias & Fairness — fairness/robustness evaluation

**Gap:** no fairness, bias, or robustness metric (demographic parity,
disparate impact, adversarial-input robustness, or otherwise) is tracked
anywhere in the eval framework.

**Trigger:** a tenant app whose domain has a real fairness exposure (e.g.
anything making decisions about people — lending, hiring, eligibility) —
genuinely not applicable to the current reference examples (oil price
forecasting has no fairness dimension), so building this speculatively
means designing metrics with no real domain to validate them against.

**Fix sketch, when triggered:** this is the one gap that likely needs a
**separate evaluation dataset**, not just a new judge-criteria dimension —
fairness test sets (e.g. paired inputs differing only in a protected
attribute, checking for outcome parity) don't usually overlap with
task-correctness golden sets. Scope as its own `.agent-rfc/fixtures/`
sibling (e.g. `fairness_evals.json`) with its own judge criteria, evaluated
by `scripts/run-evals.py --suite fairness` (new flag) rather than folded
into the existing correctness scorecard.

---

## Resolved questions (kept for the rationale, not as open items)

All three were genuinely open before P1c/P4 landed; recording how each was
settled so a future session doesn't re-litigate them from scratch.

1. **Shadow eval Phoenix access in CI** — resolved as *neither* option
   verbatim: `shadow-eval.yml` itself stays schedule-only (opt-in nightly
   cron, never run on every PR — a live tenant Phoenix isn't available in
   that context). CI coverage instead comes from
   `scripts/test/test_shadow_eval.py` (sampling determinism/rate,
   judge-prompt shape) wired into `self-test.yml`'s `python-behaviour`
   job — tests the sampling/judging *logic* on every PR without needing a
   live Phoenix in CI at all.
2. **Widget CDN** — resolved as "defer until a domain exists": ships via
   GitHub Releases (`widget.js` as a downloadable release asset, P5.11);
   docs point at self-hosting. No CDN was ever stood up.
3. **Rollback** — resolved as "notification is enough, not mandatory":
   `rollback-notify` posts to Slack/Teams and fails the job either way;
   `ROLLBACK_COMMAND` is optional — if unset, the action prints
   platform-specific guidance instead of executing anything. Verified via
   `act` with and without the secret set (P4 acceptance criteria).

---

*Previous Part 1–4 narrative archived above under **Resolved**. `docs/archive/specs-update.md` (the original architecture-review planning doc this was merged from) was deleted as dead weight — zero functional inbound links, already marked superseded at its own top line; this file and SPECS.md's own content are the complete record. See OPERATIONS.md §12 for spec cross-reference.*
