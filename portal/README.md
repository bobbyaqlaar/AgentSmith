# Ops Portal

Cross-tenant operations dashboard for AgenticFramework (SPECS.md §15, §26).

## Purpose

The Ops Portal aggregates data across all tenant pipelines and surfaces it to the operations team. It is distinct from Arize Phoenix (per-developer trace viewer) and the In-App Widget (end-user status component).

## Audience

- Platform / operations team
- Tech leads monitoring multiple tenant deployments

## Status: v1 implemented

Tenant overview, per-tenant cost chart, unresolved-issues list, and the
history-sync ingestion endpoint are implemented and tested end-to-end against
a real Postgres instance. DLQ depth and Temporal/Celery queue metrics are
**not yet wired** — see "Known gaps" below; the UI shows this honestly
rather than fabricating data.

## Setup

```bash
cd portal
cp .env.example .env.local   # fill in DATABASE_URL, OPS_PORTAL_*
npm install
npm run db:migrate           # applies db/schema.sql
npm run dev                  # http://localhost:3000
```

`DATABASE_URL` must point at the **same** Postgres instance used by
`runtime/llm_gateway.py`'s Postgres budget backend (`BUDGET_BACKEND=postgres`)
— the portal reads the `llm_gateway_budget` table directly, read-only. It
does not duplicate cost accounting.

## Views

- **Tenant overview** (`/`) — all tenants, current-month spend, unresolved
  MAJOR/CRITICAL count, DLQ pending (or "—" if not wired)
- **Tenant detail** (`/tenants/[id]`) — cost-over-time chart (Recharts),
  unresolved issues list, link to the tenant's Phoenix instance

## API Contract

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/tenants` | GET | Basic auth | List tenants with current spend, unresolved issue count, DLQ pending |
| `/api/tenants` | POST | Basic auth | Register/update a tenant: `{ tenantId, name, isolation?, phoenixBaseUrl? }` |
| `/api/tenants/:id/cost` | GET | Basic auth | Monthly spend history for one tenant |
| `/api/tenants/:id/issues` | GET | Basic auth | Unresolved MAJOR/CRITICAL `.agent-history.log` entries for one tenant |
| `/api/dlq` | GET | Basic auth | `{ wired: boolean, pendingByTenant }` — `wired: false` until `dead_letter.py` has a persistent store |
| `/api/sync/history` | POST | `Bearer $OPS_PORTAL_SYNC_TOKEN` | Ingestion endpoint — see below |
| `/api/audit` | GET | Basic auth | List signed audit events, each with `verified: boolean` |
| `/api/audit/append` | POST | `Bearer $AUDIT_LOG_WRITE_TOKEN` | Append a signed audit event — see below |

### Audit log (SPECS.md §30, enterprise pack)

Every event is HMAC-SHA256 signed over its own fields with `AUDIT_LOG_HMAC_KEY`
(server-side secret, never exposed to clients) and the `audit_log` table has
DB-level triggers blocking `UPDATE`/`DELETE` outright — append-only at two
independent layers. `GET /api/audit` recomputes each row's signature on read
and returns `verified: false` if it doesn't match, which catches tampering
even by someone with direct database access who disabled the trigger.
Verified live against a real Postgres instance, including a simulated
privileged-attacker scenario (disable trigger → mutate row → re-enable
trigger) — the signature layer still flags the altered row.

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" http://localhost:3000/api/audit?tenantId=acme

curl -X POST http://localhost:3000/api/audit/append \
  -H "Authorization: Bearer $AUDIT_LOG_WRITE_TOKEN" -H "Content-Type: application/json" \
  -d '{"eventType":"hitl_promotion","actorId":"bobby@example.com","tenantId":"acme","details":{"from":"staging","to":"production"}}'
```

`eventType` must be one of `hook_bypass | hitl_promotion | config_change | tenant_created`.

Wired call sites: `ai-tenant-init` (writes `tenant_created`) and
`ai-tenant-promote` (writes `hitl_promotion`) in `install-ai-stack.sh` POST
here when `OPS_PORTAL_URL` and `AUDIT_LOG_WRITE_TOKEN` are set in the
developer/CI environment — best-effort, never blocking the command if the
portal is unreachable or unconfigured. `hook_bypass` and `config_change` are
documented extension points for the enterprise break-glass flow and Ops
Portal admin actions respectively, not yet wired from a concrete caller.

### SSO/OIDC (SPECS.md §30, enterprise pack)

`SSO_ENABLED=true` **replaces** (not augments) HTTP basic auth for the
dashboard with an OIDC authorization-code+PKCE login flow. Machine-to-machine
endpoints (`/api/sync/*`, `/api/widget/*`, `/api/audit/append`) are
unaffected either way — they were never gated by basic auth.

```bash
SSO_ENABLED=true
SSO_ISSUER=https://corp.okta.com
SSO_CLIENT_ID=...
SSO_CLIENT_SECRET=...
SSO_REDIRECT_URI=https://ops.example.com/api/auth/callback
SSO_SESSION_SECRET=<random 32+ byte string>
```

Session is a stateless HMAC-signed JWT cookie (`jose`, HS256), not a server
session store — same signed-token pattern used elsewhere in this app (widget
tokens, sync tokens), no new infra dependency. `GET /api/auth/login`,
`GET /api/auth/callback`, `POST /api/auth/logout`.

Verified end-to-end against a real local OIDC provider (`oidc-provider` npm
package, authorization-code+PKCE flow, login+consent interactions) — not
just unit-tested. This surfaced and fixed two real bugs during
implementation:
- `next start` always sets `NODE_ENV=production` regardless of whether TLS
  is actually present, so cookies were incorrectly marked `Secure` during
  local-HTTP testing and silently never sent back, breaking the whole flow
  with no clear error. Fixed by tying the `Secure` flag to the same explicit
  `SSO_ALLOW_INSECURE_HTTP` opt-in used for the OIDC discovery request,
  instead of inferring it from `NODE_ENV`.
- A hand-rolled `Cookie` header parser in the callback route didn't
  URL-decode values, so the `oidc_redirect_to` cookie's `%2F` was used
  literally instead of being decoded to `/`, sending every successful login
  to a 404 at `.../%2F` instead of the dashboard. Fixed by switching to
  `next/headers`' `cookies()`, which decodes correctly.

`SSO_ALLOW_INSECURE_HTTP=true` is for local dev/testing against a non-TLS
IdP only — never set it in a real deployment; it disables openid-client's
default (correct) requirement that the issuer be HTTPS.

### History sync contract

Tenant CD workflows (or a local `ai-stack-check` run) POST unresolved/changed
`.agent-history.log` entries here. Upsert is idempotent on `(tenantId, entryId)`,
so it's safe to re-send the same entries on every sync — and re-sending an
entry with `hitlResolved: true` clears it from the unresolved count.

```bash
curl -X POST https://ops.example.com/api/sync/history \
  -H "Authorization: Bearer $OPS_PORTAL_SYNC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenantId": "acme",
    "entries": [
      { "entryId": "<id>", "level": "CRITICAL", "event": "...", "timestamp": "2026-06-20T10:00:00Z", "hitlResolved": false, "raw": { } }
    ]
  }'
```

A tenant is auto-registered on its first sync — no separate provisioning
step required before a new tenant's CD pipeline can push history.

## Auth

- **Dashboard** (`/`, `/tenants/*`, `/api/tenants*`, `/api/dlq`): HTTP Basic
  auth via `OPS_PORTAL_USER` / `OPS_PORTAL_PASSWORD`. The portal refuses to
  serve traffic if either is unset — no unauthenticated team-shared
  deployment (mirrors the Phoenix requirement in §15).
- **Sync ingestion** (`/api/sync/history`): separate bearer token
  (`OPS_PORTAL_SYNC_TOKEN`), since this is called by CI runners across every
  tenant repo, not by a human browsing the dashboard.
- Enterprise pack: SSO/OIDC replaces basic auth (see SPECS.md §30) — not yet
  implemented here.

## Data Sources

1. **Cost** — reads `llm_gateway_budget` (owned by `runtime/llm_gateway.py`'s
   Postgres backend) directly, read-only.
2. **Unresolved issues** — `agent_history_entries`, populated via the sync
   endpoint above.
3. **DLQ depth** — `dlq_entries`, **not created by this app's migration**.
   `runtime/dead_letter.py` has no persistent store implementation yet
   (Phase 2 follow-up). Once it does, it should create a `dlq_entries` table
   with the column shape documented in `db/schema.sql` and the portal will
   start reporting real depth with no code changes.
4. **Phoenix** — `lib/phoenix.ts` currently does a health check and builds a
   tenant-scoped deep link. Trace/experiment aggregation via Phoenix's
   GraphQL API is a follow-up once a live tenant Phoenix instance is
   available to develop against.
5. **Workflow engine queue depth** (Temporal/Celery) — not yet implemented.

## Known gaps (intentionally not faked)

- DLQ depth shows `wired: false` / `—` until `dead_letter.py`'s store exists.
- Queue depth (Temporal/Celery) is not implemented.
- Phoenix integration is health-check + deep-link only, not full trace
  aggregation.
- No SSO — basic auth only, per the "team deployment" tier in §15.

## Tech Stack

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS
- Recharts (cost chart)
- `pg` (node-postgres) against the shared framework Postgres instance
