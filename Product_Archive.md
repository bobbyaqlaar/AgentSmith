# AgentSmith — Product Build Archive

**Purpose:** Authoritative record of every implementation PR, design
decision, and acceptance-criteria audit from P0 through P9. This is a
read-only historical log — do not re-open items here unless a regression
has been identified. Active work lives in `FIXES_AND_CLEANUP.md`.

---

## Build complete (2026-06-23)

All four originally-deferred items (P1b, P1c, P2, P4) plus the P0.5
infra/design work are done and verified against the live Docker stack.

### Live infra — already running, do NOT recreate from scratch

```
agenticframework-db        Postgres 16, container, healthy   — 127.0.0.1:55432
agenticframework-phoenix   Phoenix, container, healthy       — http://localhost:6006
agenticframework-portal    Ops Portal, container, healthy    — http://localhost:3000
```

Check with `docker compose ps` from the repo root. Credentials are in the
repo-root `.env` (gitignored). Two logical databases on
`agenticframework-db`: `phoenix` (Phoenix's own) and `agenticframework`
(Ops Portal + runtime data — tenants, audit_log, agent_runs, etc.).
One real tenant already registered: `acme`, `phoenixBaseUrl:
http://phoenix:6006` (internal docker hostname), `budget_cap_usd: 250.5`.

After pulling any new schema.sql changes: **rebuild before migrating** —
`docker compose build portal && docker compose run --rm portal npm run
db:migrate`. The image bakes in `schema.sql` at build time; running
migrate against a stale image silently no-ops new columns.

### Status of the deferred items + infra/design work

| Item | Status |
|---|---|
| P0.5a (containerize portal) | ✅ Done — `portal/Dockerfile`, `next.config.mjs` standalone output, `docker-compose.yml` `portal` service, `init-db/01-create-agenticframework-db.sh` |
| P0.5a-design (visual redesign) | ✅ Done — light/dark toggle (`components/ui/ThemeToggle.tsx`), `Card`/`Badge`/`MetricCard` in `components/ui/`, breadcrumb on tenant detail, new `/dlq` and `/audit` pages, restyled `CostChart`. Verified live in a real browser, both themes, all 4 pages. |
| P0.5b (vendor + machine-wide lifecycle) | ✅ Done — `install-ai-stack.sh` vendors `docker-compose.yml`+`init-db/`+`portal/` to `~/.agent-framework/observability/`; `ai-dashboard-start`/`-stop` redefined to manage the compose stack with a plain-process-Phoenix fallback. Tested against a scratch `$HOME`. |
| P0.5c (per-repo opt-out) | ✅ Done — `.agenticframework/no-shared-infra` marker, checked in `ai-dashboard-start` and `ai-tenant-init`'s output. Tested both branches. |
| P1b (CD → portal history sync) | ✅ Done — `scripts/sync-portal-history.py` (new), wired into `cd-staging.yml`/`cd-production.yml`/`ai-stack-check`, `verify_system.py --check-history-sync`. Verified live against the running portal. |
| P2a (`agent_runs` + real run status) | ✅ Done — `agent_runs` table, `POST /api/runs/ingest`, `runtime/llm_gateway.py` emits running/success/degraded/failed via `_report_run_status`, `portal/lib/runStatus.ts` prefers it. Also required a `middleware.ts` matcher fix (added `api/runs/ingest` to the unauthenticated machine-to-machine exclusion list). Verified live: a real `LLMGateway.complete()` call landed a `success` row, `GET /api/widget/status` reflected it. |
| P2b (cost cap from tenant.yaml) | ✅ Done — `tenants.budget_cap_usd` column (needed an explicit `ALTER TABLE ADD COLUMN IF NOT EXISTS`), `lib/tenants.ts`/`lib/cost.ts` updated, `/api/sync/history` accepts optional `budgetCapUsd`. Bug fixed: update path was clobbering `name` back to raw `tenantId` on every cap sync — fixed by fetching `existingTenant.name` first. Verified: `GET /api/tenants/acme/cost` returns `"cap":250.5`, `acme`'s `name` field is `"Acme"`. |
| P2c (Phoenix GraphQL query depth) | ✅ Done — `portal/lib/phoenix.ts`'s `getRecentTraceStats()` queries live Phoenix's `projects` + `Project.traceCountByStatusTimeSeries`, rendered on tenant detail page. Unit test with mocked fetch (`portal/test/phoenix.test.ts`) added to `npm test`. |
| P1c (shadow eval sampler) | ✅ Done — `scripts/eval_judge.py` (judge logic factored out), `scripts/shadow-eval.py` (new), `portal/lib/promotions.ts` (new), tenant detail page renders suggestions, `workflow-templates/shadow-eval.yml` (new, opt-in nightly cron). Verified live: 6 real OTLP spans pushed, sampled, annotated idempotently. CI regression: `scripts/test/test_shadow_eval.py` wired into `self-test.yml`'s `python-behaviour` job. |
| P4 (CD deploy/rollback automation) | ✅ Done — `.github/actions/deploy-placeholder/action.yml` and `.github/actions/rollback-notify/action.yml` wired into both CD workflows. Verified live via `act`. `OPERATIONS.md` §D.5 "Wire your platform" added. |
| Final verification pass | ✅ Done — `find … -name "*.py" | xargs py_compile`, `bash -n`/`zsh -n install-ai-stack.sh`, portal `tsc --noEmit && npm test && npm run build`, both `verify_system.py --check-redaction` profiles, widget `npm test`, `runtime/test/` + `scripts/test/` pytest against a throwaway Postgres, `verify_system.py --check-idempotency/--check-dlq/--check-hooks/--check-history-sync`. One real bug fixed: portal healthcheck used `nc -z localhost 3000` but Next's standalone server only binds IPv4 — changed to `127.0.0.1`. |

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

Legacy repos with `.github/workflows/cd-deploy.yml` get a warning on next
`post-checkout` — delete that file manually and rely on `cd-staging.yml` /
`cd-production.yml`.

---

## Resolved — no PR needed

The original adversarial review (Part 1–2, much of Part 4) has been implemented.
Do not re-open these unless a regression is found.

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

- **2.3 HITL blob I/O errors:** missing encryption key raises; transient storage failures log ERROR and may leave dangling `hitl_blob_ref`. Acceptable for v1.
- **2.3 config vs I/O:** acceptable for v1; a retry queue is a future option.

---

## Completed — second implementation pass (2026-06-23)

| ID | Topic | Resolution |
|----|-------|------------|
| P0 | Idempotency store | `runtime/idempotency.py` `_RedisBackend`/`_PostgresBackend` implemented; `llm_gateway.py` logs lookup/write failures |
| P0 | Dead-letter queue | `runtime/dead_letter.py` Postgres-backed `enqueue`/`list`/`replay`/`discard`; `replay()` takes optional `replay_handler` callback |
| P0 | DLQ activity wiring | `examples/oil-price-agent/workflows/activities.py`'s `dead_letter_activity` uses real backend |
| P0 | Idempotency key emission | `run_prediction_activity` passes `idempotency_key=make_key(...)` keyed on workflow_run_id + activity name + actual input |
| P0 | CI checks | `scripts/verify_system.py --check-idempotency` / `--check-dlq`, run against throwaway Postgres in `self-test.yml`'s `python-behaviour` job |
| P1a | Hook opt-in gate | `hooks/pre-commit`/`commit-msg`/`post-commit` no-op unless `.agenticframework/enabled`, `tenant.yaml`, or org policy exists; `hooks/post-checkout` writes the `enabled` marker on first provision |
| P1a | Enterprise RFC gate | `pre-commit` requires ≥1 RFC under `.agent-rfc/` when org policy present; `commit-msg` requires `RFC-NNN` reference |
| P1a | CI check | `scripts/verify_system.py --check-hooks` simulates both opt-in and enterprise-RFC scenarios |
| P3 | Portal behavior tests in CI | `self-test.yml`'s `portal` job runs `npm test` and `npm run test:db` (`portal/test/auditLog.test.ts`) against a real Postgres service |
| P3 | Runtime behavior tests | `runtime/test/test_llm_gateway_budget.py` and `test_trace_redactor.py` — both run via pytest, added to `requirements.txt` |
| 5.2 | `install-ai-stack.sh --mode` | `developer` (default) / `enterprise` flag |
| 5.10 | `<org>` placeholder | Replaced with `YOUR_ORG` + overridable `AI_STACK_FRAMEWORK_REPO` env var |
| 5.11 | Widget CDN | `cdn.agenticframework.io` was never a real hosted domain — docs point at self-hosting; `release.yml` ships `widget.js` as a downloadable release asset |
| 5.12 | `runtime/worker.py` | `TENANT_WORKER_MODULE` env var dispatch |

All verified against live infra before being marked done.

---

## Verification note (2026-06-23)

Every claim in this file was checked directly against the codebase before
acting on it. Two corrections from the prior draft:

- **P5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9 were already implemented** in the
  second fix pass (mapped 4.9, 4.11, 4.7/4.8, 4.6, 4.4, —, 4.13
  respectively). Re-checked directly in `install-ai-stack.sh`,
  `hooks/post-commit`, `portal/app/api/tenants/route.ts`,
  `scripts/cost_router.py`, `runtime/k8s/dedicated-tenant/configmap.yaml`,
  and `.github/workflows/release.yml`.
- **P3's problem statement overstated the gap.** `self-test.yml`'s
  `widget` job already runs `npm test` (the real XSS-regression behavioral
  suite). The actual gap was narrower: no `npm test` in the `portal` job and
  no Postgres-backed Python test job.
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

### Problem (resolved)

`runtime/idempotency.py` and `runtime/dead_letter.py` raised `NotImplementedError`.
Duplicate LLM calls were not suppressed; failed activities could not be replayed.

### Acceptance criteria

- [x] `IDEMPOTENCY_BACKEND=postgres` + `DATABASE_URL`: second `complete()` with same key returns cached result without provider call
- [x] `DeadLetterQueue.enqueue()` persists row; `GET /api/dlq` returns the row
- [x] `replay(task_id)` marks replayed; re-enqueues via optional `replay_handler` callback
- [x] OPERATIONS.md §D.4 "Known gap" paragraph replaced with setup instructions
- [x] Postgres-backed pytest passes — wired into `self-test.yml`'s `python-behaviour` job

---

## P1 — Spec/code alignment: hooks, CD sync, shadow evals ✅ done

**Branch:** `feat/spec-alignment-hooks-cd-shadow`

### P1a — Developer opt-in + enterprise RFC hooks ✅ done

| File | Change |
|------|--------|
| `hooks/pre-commit` | Opt-in gate; if org policy present: require ≥1 RFC under `.agent-rfc/*.md` |
| `hooks/commit-msg` | Same opt-in gate; if org policy present, require `RFC-NNN` in commit message |
| `hooks/post-commit` | Same opt-in gate |
| `hooks/post-checkout` | **Not gated** (deliberate deviation) — bootstrap step that provisions `enabled` marker |
| `scripts/verify_system.py` | `--check-hooks` simulates opt-in / RFC block in throwaway git repos |

**Note on the RFC split:** pre-commit runs before the commit message exists.
The precise per-commit RFC-NNN check lives in `commit-msg` instead.

**Acceptance criteria** — all met:
- [x] Repo without `.agenticframework/enabled` and without org policy: hooks no-op
- [x] Repo with `enabled` + org policy: commit without RFC reference blocked

### P1b — CD history sync to Ops Portal ✅ done

| File | Change |
|------|--------|
| `scripts/sync-portal-history.py` | New — parses `.agent-history.log` since last sync, POSTs to `OPS_PORTAL_URL/api/sync/history` |
| `workflow-templates/cd-staging.yml` | Optional step when secrets present |
| `workflow-templates/cd-production.yml` | Same |
| `install-ai-stack.sh` | `ai-stack-check` calls sync when `OPS_PORTAL_*` env vars set |

**Acceptance criteria** — all met:
- [x] Push with secrets configured → portal shows tenant issues without manual curl
- [x] Missing secrets → step skipped with warning (does not fail CD)

### P1c — Shadow eval sampler ✅ done

| File | Change |
|------|--------|
| `scripts/shadow-eval.py` | New — samples N% of Phoenix spans; async LLM judge; writes Phoenix annotations with `eval.type=shadow` |
| `workflow-templates/shadow-eval.yml` | Optional nightly/cron |
| `portal/lib/promotions.ts` | New — reads failed shadow scores → suggested promotion list |
| `portal/app/tenants/[id]/page.tsx` | Renders suggestions queue |

**CI decision:** `shadow-eval.yml` is schedule-only; per-PR coverage via
`scripts/test/test_shadow_eval.py` in `self-test.yml`'s `python-behaviour` job.
A live tenant Phoenix is not available in generic CI — this was the right call.

**Acceptance criteria** — all met:
- [x] `python3 scripts/shadow-eval.py --sample-rate 0.05` runs without blocking prod
- [x] Portal tenant detail shows ≥0 suggestions when shadow failures exist

---

## P2 — Ops Portal v2: run status, cost cap, Phoenix depth ✅ done

**Branch:** `feat/portal-run-status-phoenix`

### Problem (resolved)

Widget status was inferred from last history entry only. Cost cap always `null`.
Phoenix integration was health-check + link only.

### Acceptance criteria — all met

- [x] Widget can return `running` when an open run exists in `agent_runs`
- [x] Tenant cost page shows cap + % used when `tenant.yaml` defines `gateway.budget_cap_usd`
- [x] Tenant page shows Phoenix error rate (last 24h) when `phoenix_base_url` configured
- [x] OPERATIONS.md §F "Known gap" updated

---

## P3 — CI behaviour tests (self-test expansion) ✅ done

**Branch:** `feat/self-test-behaviour`

### Problem (resolved)

The `portal` CI job ran `tsc --noEmit && npm run build` but never `npm test`,
so `authz.test.ts` wasn't in CI. No Postgres-backed Python behavioral tests.

### Acceptance criteria — all met

- [x] PR to `main` runs all new jobs green
- [x] Regression in RBAC (`authz.test.ts`) fails CI
- [x] Redaction regression fails CI — `--check-redaction` wired into `python` job

---

## P4 — CD/deploy templates and rollback scaffolding ✅ done

**Branch:** `feat/cd-deploy-scaffolding`

### Problem (resolved)

Deploy steps were placeholders. Rollback was echo-only. Legacy `cd-deploy.yml`
caused confusion. Platform-specific deploy needed clearer extension points.

### Acceptance criteria — all met

- [x] `ai-tenant-init` never copies `cd-deploy.yml` (file removed)
- [x] Production smoke failure fails the workflow **and** runs rollback-notify action — verified via `act`
- [x] Tenant can set `DEPLOY_COMMAND` secret without editing workflow YAML

**Design decision (settled):** rollback notification and job-failure are
mandatory regardless of whether `ROLLBACK_COMMAND` is set — if unset, the
action prints platform-specific guidance instead of executing anything. The
human escalation is always required; the automation is optional.

---

## P5 — Repo hygiene and remaining cleanup ✅ done

| ID | File | Change |
|----|------|--------|
| ~~5.1~~ | ~~`.gitignore`~~ | **Done** — root ignore file added |
| ~~5.2~~ | ~~`install-ai-stack.sh`~~ | **Done** — `--mode developer\|enterprise` |
| ~~5.3–5.9~~ | Various | **Done** — were already implemented in second fix pass (see Verification note) |
| ~~5.10~~ | ~~`Readme.md`, `install-ai-stack.sh`, `UserManual.md`~~ | **Done** — `YOUR_ORG` + `AI_STACK_FRAMEWORK_REPO` |
| ~~5.11~~ | ~~`templates/in-app-widget/`~~ | **Done** — `widget.js` shipped as release asset; docs point at self-hosting. **No CDN domain exists** (`cdn.agenticframework.io` was never a real hosted domain); self-hosting from tagged release is the supported path. |
| ~~5.12~~ | ~~`runtime/worker.py`~~ | **Done** — `TENANT_WORKER_MODULE` dispatch |

---

## P6 — CI/CD industry-parity + on-prem/air-gapped deployment ✅ done (2026-06-23)

| Item | Change |
|---|---|
| Formatter gate (Python CI) | `ruff format --check .` added to `ci-python-fastapi.yml` |
| Containerize + push to GHCR | New `.github/actions/build-push-ghcr/` composite action — exports `$IMAGE_REF` for `DEPLOY_COMMAND`; skips cleanly if no `Dockerfile` |
| On-prem/air-gapped canary + shadow traffic | New `templates/onprem-deploy/` — Docker Compose path (Traefik or Envoy) + Kubernetes/Helm path (Gateway API `backendRefs[].weight` for canary, `RequestMirror` for shadow); air-gapped bundling via `docker save`/`docker load` |

**Known limitation (documented):** core K8s Gateway API's `RequestMirror`
filter has no percentage field (always mirrors 100%); partial-percentage
shadow on K8s requires a vendor extension intentionally excluded to keep
the chart portable — see `templates/onprem-deploy/kubernetes/README.md`.

---

## P7 — Code-review fixes + HITL/DLQ redesign ✅ done (2026-06-23/24)

### Code-review fixes (confirmed regressions)

| Bug | Fix | Verified |
|---|---|---|
| `cd-production.yml`'s `permissions: {contents: read}` silently broke the "Open PR for fixture updates" step (needs `git push`/`gh pr create`) | `contents: write` + `pull-requests: write` | YAML parses; reasoning verified against the step's actual calls |
| `templates/onprem-deploy/scripts/up.sh`: `"${PROFILE_ARGS[@]}"` on an empty array throws "unbound variable" under `set -u` on bash <4.4 (macOS's stock `/bin/bash`, 3.2) | `${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}` | Reproduced on bash 3.2, confirmed fix |
| `templates/onprem-deploy/kubernetes/templates/db-statefulset.yaml` renders `secretRef.name: ` (empty) when `withDb.enabled=true` but `credentialsSecretName` unset | Wrapped in Helm's `required` — fails fast with a clear message | `helm template` confirmed |

Three additional findings implemented as deeper fixes (not just patched):

| Finding | Fix |
|---|---|
| `llm_gateway.py`'s `run_id` was reused across every `complete()` call within one `workflow_id` | `run_id` is now unique per call; `workflow_id` now actually transmitted to `/api/runs/ingest`; `portal/lib/runStatus.ts` aggregates a workflow's calls ("running" if any open — covers sequential AND concurrent fan-out) |
| `render-{traefik,envoy}-config.py` accepted out-of-range weights | Both scripts validate 0-100 and exit 1 before rendering |
| `dead_letter_activity` generated a fresh UUID per Temporal retry call | `DeadLetterQueue.enqueue()` is idempotent on `task_id` (`ON CONFLICT DO NOTHING`); activity derives stable `task_id` from `workflow_run_id` |

### HITL/DLQ redesign

Temporal durable execution was the right fit — the framework already had
the primitive (`workflow.wait_condition` + a signal), it just needed
generalising. Closes 5 gaps in the prior HITL/DLQ implementation:

| Gap | Fix |
|---|---|
| "Replay" didn't actually replay anything — the timed-out workflow had already terminated | **New** `run_with_recoverable_step` (`runtime/workflows/base_workflow.py`) — on activity failure, workflow stays **alive**, parked on a per-`gate_id` signal. `runtime/temporal_replay.py`'s `make_temporal_replay_handler(client)` signals the live workflow. |
| No structured failure reason | `dlq_entries.reason` (`validation_error`/`tool_call_error`/`hitl_timeout`/`hitl_rejected`/`infra_error`) |
| Hardcoded 24h timeout | `run_with_recoverable_step(..., timeout=...)` is caller-supplied |
| One global boolean signal — no way to know which gate a signal answers | `gate_id` keys both the DLQ entry and the `human_fix_payload` signal |
| No notification on timeout | `DeadLetterQueue.enqueue()` posts to `SLACK_WEBHOOK_URL`/`TEAMS_WEBHOOK_URL` on every new entry |

**Portal-to-worker bridge design decision (settled):** the portal HMAC-signs
the edited payload and POSTs it to that tenant's own `replay_webhook_url`
(synced from `tenant.yaml`'s `hitl.*` section) rather than signaling
Temporal directly from the portal. Reasons: (1) `replay_handler` is
engine-agnostic — a Celery-based tenant implements the same extension
point without Temporal; (2) per-tenant routing means a fix always reaches
the team running that tenant's worker.

**Real bug caught by live testing:** without `retry_policy=RetryPolicy(maximum_attempts=1)` on the gated `execute_activity` call, Temporal's default retry policy retried the same failing payload indefinitely until `start_to_close_timeout` — the recoverable-step logic never engaged. Caught via a real `temporalio.testing.WorkflowEnvironment` run that hung; fixed and re-verified.

All verified live: real throwaway Postgres, real Temporal test server, real Ops Portal container.

---

## Suggested merge order (all merged)

| Order | PR | Status |
|-------|-----|--------|
| 1 | P0 | ✅ done |
| 2 | P3 | ✅ done |
| 3 | P1a + P1b | ✅ done |
| 4 | P1c | ✅ done |
| 5 | P2 | ✅ done |
| 6 | P4 | ✅ done |
| 7 | P5 | ✅ done |

---

## Verification checklist (standard, every PR)

From OPERATIONS.md §9:

```bash
find scripts runtime examples -name "*.py" -print0 | xargs -0 -n1 python3 -m py_compile
bash -n install-ai-stack.sh && zsh -n install-ai-stack.sh
cd portal && npx tsc --noEmit && npm test && npm run build
ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction
cd templates/in-app-widget && npm test
```

After P0 stores are in:

```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test -p 55432:5432 postgres:16-alpine
export DATABASE_URL="postgresql://test:test@localhost:55432/test"
pytest runtime/test/ -q
docker rm -f pg-test
```

---

## P9 — Redundancy/staleness cleanup ✅ done (2026-06-25)

Found by a full-repo review hunting for duplicate/dead code and stale docs.

| Item | Change |
|---|---|
| Duplicate helpers across `scripts/*.py` | **New** `scripts/_shared.py` — `_repo_root()` (was byte-identical in 10 files), `_iso_now()` (4 files), `_tenant_id()` (2 files), `_phoenix_get`/`_phoenix_post` (2 files). Deliberately NOT shared with `runtime/llm_gateway.py` — `runtime/` is vendored independently of `scripts/`. |
| `tenacity` imported but not used | `runtime/llm_gateway.py`'s `_invoke()` now retries `httpx.TransportError`/429/5xx with exponential backoff (`stop_after_attempt(3)`, `wait_exponential`) — the degrade-ladder "throttle" step the module's own docstring described but never implemented. Non-retryable errors (401, 400, etc.) fail on first attempt. Regression tests added. |
| `OilPricePredictionWorkflow` reimplemented `BaseAgentWorkflow` signal pattern inline | Now actually `class OilPricePredictionWorkflow(BaseAgentWorkflow)` — inherits `hitl_approved`/`self._hitl_approved`. `decide_action_activity` wrapped in `run_with_recoverable_step`. `sys.path.insert` calls moved from `oil_price_workflow.py` to `worker.py` (Temporal sandbox restriction on `Path.resolve()` at module top level — a real `RuntimeError: Failed validating workflow` caught by running against a Temporal test server). Verified live end-to-end. |
| `docs/archive/specs-update.md` (940 lines, zero functional inbound links, already marked superseded) | Deleted, along with now-empty `docs/archive/` directory. Two stale references fixed. |

Three items deliberately left open pending discussion (not ignored — see the
review conversation for pros/cons): 3-way duplicated Caddy/TLS setup across
`docker-compose.yml`/`OPERATIONS.md`/`docs/team-observability.md`, whether
`openinference-instrumentation-*` should be wired up or dropped, and whether
`prophet`/`pandas`/`numpy` should be removed now or kept for the oil-price
example's still-TODO real forecasting model.

---

## P10 — Ten Pillars enforcement gaps in CI/CD ✅ done (2026-06-30)

Surfaced by a systematic audit of all ten operational pillars (SPECS.md §4)
against the tenant CI workflows. All four gaps were **CI absences** — the
local hook layer enforced them, but CI did not mirror the enforcement,
meaning a PR that bypassed local hooks would pass CI undetected.

| Sub-item | Gap | Resolution |
|---|---|---|
| P10a (Pillar 2 🔴) | `map_codebase.py` never invoked in CI — KG could be stale | Added `Validate Knowledge Graph` step to all three `ci-*.yml` templates (`continue-on-error: true`); added `--check-kg` flag to `verify_system.py` wired into `self-test.yml` |
| P10b (Pillar 1 🔴) | RFC gate absent from CI — bypassed hooks let RFC-less PRs through in enterprise mode | Added `RFC gate` step to all three `ci-*.yml` templates (no-op in developer mode, enforced when `org-policy.yaml` present) |
| P10c (Pillar 6/7 🟡) | IDE config drift (`.cursorrules`, `CLAUDE.md`) undetected in CI | Added `IDE config drift check` step calling `generate-ide-config.py --check-only` (`continue-on-error: true`) |
| P10d (Pillar 3/5 🟢) | `verify_system.py` absent from tenant CI (partial gap — CD already ran `--check-redaction`) | Added non-blocking `Framework health check` step to all three `ci-*.yml` templates |

**Also fixed in this phase:** `set +e` required before `pytest` exit-code
capture in `ci-python-fastapi.yml` — the `run:` block's implicit `set -e`
aborted on pytest's non-zero exit before `code=$?` was ever reached,
silently making the "exit 5 = no tests" tolerance dead code. Fixed in PR #16.

**Acceptance criteria — all met:**
- [x] Every `ci-*.yml` runs `map_codebase.py` and logs KG node/edge count
- [x] Enterprise-mode PRs without an RFC file fail CI (not just the local hook)
- [x] `generate-ide-config.py --check-only` warns on IDE config drift in CI
- [x] `verify_system.py` non-blocking call in all tenant CI workflows
- [x] `verify_system.py --check-kg` added and wired into `self-test.yml`

---

## Resolved design questions (P1c/P4/P5)

These were genuinely open before their respective PRs landed. Recorded so
they are not re-litigated.

1. **Shadow eval Phoenix access in CI** — resolved as neither option verbatim:
   `shadow-eval.yml` is schedule-only (opt-in nightly cron, never per-PR — a
   live tenant Phoenix isn't available in that context). CI coverage comes from
   `scripts/test/test_shadow_eval.py` (sampling determinism/rate, judge-prompt
   shape) wired into `self-test.yml`'s `python-behaviour` job.

2. **Widget CDN** — resolved as "defer until a domain exists": ships via GitHub
   Releases (`widget.js` as a downloadable release asset, P5.11); docs point at
   self-hosting. `cdn.agenticframework.io` is not a real hosted domain.

3. **Rollback** — resolved as "notification is enough, not mandatory":
   `rollback-notify` posts to Slack/Teams and fails the job either way;
   `ROLLBACK_COMMAND` is optional — if unset, prints platform-specific guidance
   instead of executing anything. Verified via `act` with and without the secret.

---

*Active work lives in `FIXES_AND_CLEANUP.md` (Future Phases — P10 is complete).
SPECS.md and Readme.md are the canonical specification record.
OPERATIONS.md is the canonical operator-facing reference.*
