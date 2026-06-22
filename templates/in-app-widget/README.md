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

**Honest limitation:** there is no dedicated "agent run" event stream yet —
`runtime/worker.py` and `scripts/multi_agent_system.py` don't emit explicit
run-start/run-end events to the portal. Status is derived from the most
recent synced `.agent-history.log` entry instead (see
`portal/lib/runStatus.ts`), so `running` is never shown — only
`success` / `degraded` / `failed`. A real run-status table is a documented
follow-up once the worker emits that data.

## Display

- Status badge: Operational (green) / Degraded (amber) / Failed (red)
- Error summary (truncated, full text in a `title` tooltip) when degraded/failed
- Link to the tenant's Phoenix instance, if registered
- Polls every 30s by default (`poll-interval-ms` to override)

## Integration

### Vanilla (no framework)

```html
<script src="https://cdn.agenticframework.io/widget.js"></script>
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
