# Ops Portal

Cross-tenant operations dashboard for AgentSmith (SPECS.md §15, §26).
Full setup/operate walkthrough, including a click-through of every page
against a real example tenant: `OPERATIONS.md` §2.3b and Part E.

## Purpose

Aggregates data across every tenant pipeline running on this framework and
surfaces it to the operations team. Distinct from Arize Phoenix
(per-developer trace viewer, one tenant's detail at a time) and the In-App
Widget (`templates/in-app-widget/` — end-user-facing status badge, no
operator surface).

## Audience

- Platform / operations team
- Tech leads monitoring multiple tenant deployments
- Whoever's on call for HITL/DLQ triage

## Setup

```bash
cd portal
cp .env.example .env
npm install
npm run db:migrate   # applies db/schema.sql against DATABASE_URL
npm run dev           # http://localhost:3000
```

`DATABASE_URL` must point at the **same** Postgres instance used by
`runtime/llm_gateway.py`'s Postgres backend and `runtime/dead_letter.py` —
the portal reads `llm_gateway_budget`/`dlq_entries` directly, read-only for
cost, read-write for DLQ status transitions. It does not duplicate cost
accounting or own the DLQ schema (`dead_letter.py` migrates `dlq_entries`
itself, on first construction in a worker process — see "Data sources"
below for why that table is deliberately not in `db/schema.sql`).

The portal **refuses to serve traffic** without `OPS_PORTAL_USER`/
`OPS_PORTAL_PASSWORD` (or `OPS_PORTAL_USERS` for multi-user RBAC, or SSO —
see "Auth & RBAC") — there is no unauthenticated mode, on a solo-dev
machine or a shared team server.

In production, this runs as the `portal` service in the repo-root
`docker-compose.yml` (built from `portal/Dockerfile`), not via `npm run
dev` — see `OPERATIONS.md` Part B/E and `install-ai-stack.sh`'s
`ai-dashboard-start`.

## Pages

| Page | Shows |
|---|---|
| `/` — Tenant list | Every tenant in scope, current-month spend, unresolved MAJOR/CRITICAL count, DLQ pending count |
| `/tenants/[id]` — Tenant detail | Cost-over-time chart + budget cap %, real run status (`running`/`success`/`degraded`/`failed`, aggregated across a workflow's calls — see `lib/runStatus.ts`), Phoenix reachability + trace count/error rate (last 24h), unresolved issues list |
| `/dlq` — DLQ overview | Pending-entry count per tenant in scope |
| `/dlq/[tenantId]` — DLQ triage | Every pending entry for one tenant: error text, structured `reason` badge, editable JSON payload, **Replay** (signs the edit and POSTs to that tenant's own `replay_webhook_url`) and **Discard** |
| `/audit` — Audit log | Every signed admin/system event, with live tamper-detection (`verified: false` on a mismatch) |

## API

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/tenants` | GET | Dashboard (any role) | List tenants in scope, with spend/issues/DLQ counts |
| `/api/tenants` | POST | Dashboard (operator/admin) | Register/update a tenant: `{ tenantId, name, isolation?, phoenixBaseUrl?, budgetCapUsd?, replayWebhookUrl?, replayWebhookSecret? }` |
| `/api/tenants/:id/cost` | GET | Dashboard | Monthly spend history + budget cap for one tenant |
| `/api/tenants/:id/issues` | GET | Dashboard | Unresolved MAJOR/CRITICAL `.agent-history.log` entries |
| `/api/tenants/:id/widget-token` | POST | Dashboard (operator/admin) | Mint a read-only widget token — plaintext returned once |
| `/api/tenants/:id/widget-token` | DELETE | Dashboard (admin only) | Revoke every active widget token for this tenant |
| `/api/dlq` | GET | Dashboard | `{ wired: boolean, pendingByTenant }` |
| `/api/dlq/:taskId/replay` | POST | Dashboard (operator/admin, tenant in scope) | HMAC-signs `{ taskId, payload }` and POSTs it to the entry's tenant's `replay_webhook_url`; returns `{ ok, resumable }` — `resumable: false` means the entry has no `workflow_id`/`gate_id` to signal |
| `/api/dlq/:taskId/discard` | POST | Dashboard (operator/admin, tenant in scope) | Marks the entry discarded directly — safe without a webhook round-trip, since it never resumes anything live |
| `/api/runs/ingest` | POST | `Bearer $OPS_PORTAL_SYNC_TOKEN` | `runtime/llm_gateway.py`'s best-effort run-status push (`running`/`success`/`degraded`/`failed`), keyed by `runId`, grouped by `workflowId` |
| `/api/sync/history` | POST | `Bearer $OPS_PORTAL_SYNC_TOKEN` | CD-pipeline ingestion: `.agent-history.log` entries + optional `budgetCapUsd`/`replayWebhookUrl`/`replayWebhookSecret` synced from `tenant.yaml` |
| `/api/audit` | GET | Dashboard (admin only) | List signed audit events, each with `verified: boolean` |
| `/api/audit/append` | POST | `Bearer $AUDIT_LOG_WRITE_TOKEN` | Append a signed audit event |
| `/api/widget/status` | GET | `?token=` (widget token, not dashboard auth) | What the In-App Widget polls — tenant-scoped entirely by the token, never by a client-supplied tenant id |
| `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/session-status` | — | SSO/OIDC flow (only active when `SSO_ENABLED=true`) |

"Dashboard" auth above means basic auth (`OPS_PORTAL_USER`/`PASSWORD` or
`OPS_PORTAL_USERS`) or an SSO session cookie — see "Auth & RBAC."

## Auth & RBAC

Every authenticated request resolves to `Access { role, tenantScope }`
(`lib/authz.ts`) before any tenant data is read — enforced server-side in
every route under `app/api/**` and in every page component, never
client-side only.

| Role | View | Write (create/update tenants, mint widget tokens) | Revoke widget tokens | Audit log |
|---|---|---|---|---|
| `viewer` | Tenants in scope | No | No | No |
| `operator` | Tenants in scope | Yes | No | No |
| `admin` | Tenants in scope (or all, with `tenants: "*"`) | Yes | Yes | Yes |

`tenantScope` is `"*"` or an explicit tenant-id allow-list. Two auth modes,
either works standalone or together:

- **Basic auth, single user**: `OPS_PORTAL_USER`/`OPS_PORTAL_PASSWORD` —
  implicitly `admin`, `tenants: "*"`.
- **Basic auth, multi-user**: `OPS_PORTAL_USERS` — a JSON array of
  `{ username, password, role, tenants }`.
- **SSO/OIDC**: `SSO_ENABLED=true` + `SSO_ISSUER`/`SSO_CLIENT_ID`/
  `SSO_CLIENT_SECRET`/`SSO_REDIRECT_URI`, with `OPS_PORTAL_SSO_USERS`
  (keyed by email) for per-identity roles — an authenticated identity not
  listed gets `viewer` with **zero** tenant access, never an implicit-admin
  fallback. Session is a stateless HMAC-signed JWT cookie (`lib/sessionToken.ts`),
  revocable server-side (`revoked_sessions` table) on logout.

**Machine-to-machine endpoints** (`/api/sync/*`, `/api/runs/ingest`,
`/api/widget/*`, `/api/audit/append`) are excluded from the dashboard-auth
middleware entirely — each has its own bearer-token/widget-token check
inside the route handler, not basic-auth/SSO.

## Data sources

| Surface | Table/source | Owner |
|---|---|---|
| Cost | `llm_gateway_budget` | `runtime/llm_gateway.py` (read-only here) |
| Unresolved issues | `agent_history_entries` | This portal, via `/api/sync/history` |
| Run status | `agent_runs` | This portal, via `/api/runs/ingest` (pushed by `runtime/llm_gateway.py`) |
| DLQ | `dlq_entries` | **`runtime/dead_letter.py`**, not this portal's migration — it creates/migrates the table itself on first `DeadLetterQueue()` construction in a worker process. `db/schema.sql` deliberately excludes it (see that file's comment) so there's one schema owner, not two competing migrations of the same table. Until at least one worker has constructed a `DeadLetterQueue`, `GET /api/dlq` reports `wired: false` — a genuine "nothing has run against this DB yet" signal, not a placeholder. |
| Phoenix trace stats | Phoenix's own REST (health check) + GraphQL (`traceCountByStatusTimeSeries`) | Read live from each tenant's `phoenixBaseUrl`, not cached |
| Audit log | `audit_log` | This portal — HMAC-signed, DB-trigger-enforced append-only |

## Honest gaps

- **Workflow-engine queue depth** (Temporal/Celery task-queue backlog, as
  opposed to DLQ depth) is not surfaced anywhere in the portal — there's no
  page or API route for it. Would need a tenant-side exporter; out of scope
  until a concrete tenant asks for it.
- **DLQ replay's "resumable" signal is informational only at the API
  level** — the portal can't *prevent* a Replay click on a non-resumable
  entry (one with no `workflow_id`/`gate_id`, e.g. from the older
  `run_with_hitl_gate`'s terminal dead-letter); it still sends the webhook
  and reports `resumable: false` in the response, and the UI shows a
  different message for that case, but it doesn't disable the button.
- **Non-Temporal workflow engines** get the DLQ/replay mechanism's *data
  model* (structured `reason`/`workflow_id`/`gate_id`) but not a
  ready-made replay handler — `runtime/temporal_replay.py` is
  Temporal-specific; a Celery-based tenant implements the equivalent
  themselves against the same `DeadLetterQueue.replay_handler` extension
  point.

## Tech stack

- Next.js 14 (App Router) + TypeScript, standalone output (`next.config.mjs`)
- Tailwind CSS, `darkMode: "class"` with a light/dark toggle, no other UI framework
- Recharts (cost chart)
- `pg` (node-postgres) against the shared framework Postgres instance
- `jose` (signed session JWTs), `openid-client` (SSO/OIDC)
