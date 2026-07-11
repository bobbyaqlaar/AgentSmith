# In-App Widget

Embeddable end-user status component for tenant applications.

## Purpose

Displays the status of the last agent run to end users of a tenant application.
Read-only, tenant-scoped, no cross-tenant data access.

## Audience

End users of tenant applications (not developers or operations).

## Status: v1 implemented

`widget.js` and the React wrapper are implemented, unit-tested against a
real `<agent-status>` custom element (jsdom) including an XSS-attribute-
injection regression test, and wired against the Ops Portal's
`/api/widget/status` endpoint.

`running` is a reachable status (Product_Archive.md P2a/P2c) —
`runtime/llm_gateway.py`'s `complete()` posts best-effort run-start/end
events to `POST /api/runs/ingest` (gated on `OPS_PORTAL_URL`/
`OPS_PORTAL_SYNC_TOKEN` being set), landing in the portal's `agent_runs`
table. `portal/lib/runStatus.ts` aggregates every call sharing one
`workflow_id` into a single status — `running` if any call in that group
hasn't finished yet (covers a workflow with multiple/concurrent LLM
calls, not just a single one), otherwise the worst terminal status among
them. Falls back to deriving a status from the most recent synced
`.agent-history.log` entry (`success`/`degraded`/`failed` only — that
fallback path genuinely can't produce `running`) when no `agent_runs` row
exists yet for the tenant, e.g. a worker that predates this feature or
never had `OPS_PORTAL_URL` configured.

## Display

- Status badge: Operational (green) / Degraded (amber) / Failed (red)
- Error summary (truncated, full text in a `title` tooltip) when degraded/failed
- Link to the tenant's Phoenix instance, if registered
- Polls every 30s by default (`poll-interval-ms` to override)

## Integration

**No CDN exists yet** (`cdn.agenticframework.io` is not a real, hosted
domain) — self-host `widget.js` until one does. Each tagged release
publishes `widget.js` as a downloadable asset
(`.github/workflows/release.yml`) for exactly this purpose: download it,
serve it from your own app's static assets, and point the `<script>` tag at
your own URL.

### Vanilla (no framework)

```html
<!-- Self-hosted: download widget.js from a release and serve it yourself -->
<script src="/static/widget.js"></script>
<agent-status
  tenant-id="acme"
  token="<read-only-scoped-token>"
  portal-url="https://ops.example.com"
></agent-status>
```

### React

```tsx
import { AgentStatus } from "@agenticframework/in-app-widget/react/AgentStatus";

<AgentStatus tenantId="acme" token={token} portalUrl="https://ops.example.com" />
```

The React wrapper loads `widget.js` once and renders the same custom
element — it does not reimplement any logic, so behaviour is identical to
the vanilla embed.

## Getting a token

Mint one from a trusted environment (never from the browser) using the Ops
Portal's dashboard credentials:

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" \
  -X POST https://ops.example.com/api/tenants/acme/widget-token
# => { "token": "...", "note": "Store this now — it will not be shown again." }
```

## Auth & security

- **The token is the only access-control boundary.** The `tenant-id`
  attribute is a display label only — the portal resolves which tenant's
  data to return purely from the token (see
  `portal/app/api/widget/status/route.ts`). A forged `tenant-id` cannot be
  used to read another tenant's data.
- Token is opaque and stored hashed (SHA-256) server-side; only shown once
  at creation time.
- Token can be revoked/rotated without redeploying the tenant app — mint a
  new one and update the embed snippet.
- All dynamic content (error summaries, tenant labels) is escaped before
  insertion into the DOM, including HTML-attribute contexts (`title=`,
  `href=`) — see the `_escape` / `_escapeAttr` distinction in `widget.js`.
  An earlier draft used text-content escaping for an attribute value, which
  allowed attribute-injection XSS via a crafted error-summary string
  containing a `"`; this was caught by a jsdom regression test before
  shipping and is now covered by that test.

## Tech Stack

- Vanilla Web Component (`widget.js`), no framework dependency, no build step
- Single `<script>` embed
- Optional React wrapper in `react/AgentStatus.tsx`
