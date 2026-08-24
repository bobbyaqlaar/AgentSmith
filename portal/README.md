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
| `/tenants/[id]` — Tenant detail | Cost-over-time chart + budget cap %, real run status (`running`/`success`/`degraded`/`failed`, or `unknown` when nothing has been recorded at all, aggregated across a workflow's calls — see `lib/runStatus.ts`), Phoenix reachability + trace count/error rate (last 24h), unresolved issues list |
| `/dlq` — DLQ overview | Pending-entry count per tenant in scope |
| `/dlq/[tenantId]` — DLQ triage | Every pending entry for one tenant: error text, structured `reason` badge, editable JSON payload, **Replay** (signs the edit and POSTs to that tenant's own `replay_webhook_url`) and **Discard** |
| `/audit` — Audit log | Every signed admin/system event, re-verified on read. A mismatch shows as **unverified** — altered, or signed before a key rotation; the portal reports the mismatch, not a cause |

## API

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/tenants` | GET | Dashboard (any role) | List tenants in scope, with spend/issues/DLQ counts |
| `/api/tenants` | POST | Dashboard (operator/admin, **and the tenant must be in the caller's scope**) | Register/update a tenant: `{ tenantId, name, isolation?, phoenixBaseUrl?, budgetCapUsd?, replayWebhookUrl?, replayWebhookSecret? }`. Both URL fields must be `http(s)`; unknown fields are ignored rather than forwarded to the database |
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

## Tracing

Off unless `OTEL_EXPORTER_OTLP_ENDPOINT` (or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`)
is set — see `.env.example`. With it set, `instrumentation.ts` registers an OTel
provider, which also switches on Next.js's own request instrumentation and the
W3C propagator. The practical effect: the `traceparent` a worker sends on
`POST /api/runs/ingest` makes the portal's request span a **child** of the LLM
call that triggered it, so `agent_runs.trace_id` stops being the only link
between the two.

| Span | What it covers |
|---|---|
| `portal.db.<OPERATION>` | Every `pg` query — the pool itself is traced (`lib/db.ts`), so no call site opts in |
| `portal.phoenix.graphql` / `portal.phoenix.health` | Outbound calls to a tenant's Phoenix, the slowest hop the portal makes |
| `portal.runs.ingest`, `portal.sync.history` | The machine-to-machine write paths |
| `portal.dlq.replay`, `portal.dlq.discard` | Operator actions, with the acting RBAC role |

Identity follows `runtime/tracing.py`'s split: `service.name`, `project.name`,
`environment` and `agent.role=ops-portal` on the Resource; `tenant.id` and
`portal.actor.role` stamped per span from the active context, and **absent**
rather than defaulted when a request has no tenant.

Portal spans deliberately carry no request bodies, no bound query values and no
replayed payloads. The worker's spans pass through `runtime/trace_redactor.py`;
nothing stands between a portal span and the collector, so nothing that could
hold tenant data goes on one. Parameterised SQL is recorded because it is code.

## Honest gaps

- **The widget token travels in a query string.** `GET /api/widget/status?token=…`
  is called from a tenant's own page, so the token lands in access logs and in
  any `Referer` a redirect might carry. Moving it to a header means a CORS
  preflight and a breaking change for every embed already in the wild, so it
  stays for now — mint per-tenant tokens, and revoke via
  `DELETE /api/tenants/:id/widget-token` if one leaks. The token grants
  read-only status for one tenant and nothing else.

- **The portal fetches URLs its operators supply.** `phoenix_base_url` and
  `replay_webhook_url` are validated as `http(s)` and nothing more: the intended
  deployments are `http://phoenix:6006` and `http://localhost:6006`, so a
  private-address blocklist would reject the product's own defaults. What bounds
  it is who may write those fields — an operator or admin, and only for tenants
  inside their own scope (`POST /api/tenants`). Treat portal operator as a
  trusted role with outbound network reach from the portal's host.

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
- OpenTelemetry (`sdk-trace-node` + OTLP/HTTP exporter), loaded only in the Node
  runtime — `middleware.ts` compiles to the Edge runtime, which cannot load it
