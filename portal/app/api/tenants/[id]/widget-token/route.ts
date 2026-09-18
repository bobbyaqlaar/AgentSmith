// POST /api/tenants/:id/widget-token — mint a new read-only widget token for
// a tenant (docs/DESIGN.md › Federated Observability). Minting requires `operator` or `admin` (an
// operator's day-to-day job includes onboarding a tenant's widget, same
// tier as creating tenants via POST /api/tenants); revoking requires
// `admin` only, since it instantly breaks every live embed for that
// tenant — a more disruptive action than minting a new one. Both also
// require the caller's grants to cover this tenant id. Protected
// by the dashboard's basic auth (this route is NOT in middleware's
// exclusion list). The plaintext token is returned exactly once; only its
// hash is persisted — losing it means minting a new one and updating the
// tenant app's embed snippet.

import { NextResponse } from "next/server";
import { createWidgetToken, revokeWidgetTokensForTenant } from "@/lib/widgetTokens";
import { getTenant } from "@/lib/tenants";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!can(access, "ops.widget")) {
    return NextResponse.json({ error: "Operator or Administrator role required to mint widget tokens" }, { status: 403 });
  }
  if (!can(access, "ops.widget", params.id)) {
    return NextResponse.json({ error: `Unknown tenant ${params.id}` }, { status: 404 });
  }

  const tenant = await getTenant(params.id);
  if (!tenant) {
    return NextResponse.json({ error: `Unknown tenant ${params.id}` }, { status: 404 });
  }
  const token = await createWidgetToken(params.id);
  return NextResponse.json({
    token,
    note: "Store this now — it will not be shown again. Embed it via the <agent-status token=\"...\"> attribute.",
  });
}

// Revokes every still-active widget token for this tenant (see
// lib/widgetTokens.ts revokeWidgetTokensForTenant for why this is tenant-
// scoped rather than taking a specific token).
export async function DELETE(_request: Request, { params }: { params: { id: string } }) {
  const access = currentAccess();
  if (!can(access, "admin.apps")) {
    return NextResponse.json({ error: "Administrator role required to revoke widget tokens" }, { status: 403 });
  }
  if (!can(access, "admin.apps", params.id)) {
    return NextResponse.json({ error: `Unknown tenant ${params.id}` }, { status: 404 });
  }

  const tenant = await getTenant(params.id);
  if (!tenant) {
    return NextResponse.json({ error: `Unknown tenant ${params.id}` }, { status: 404 });
  }
  const revoked = await revokeWidgetTokensForTenant(params.id);
  return NextResponse.json({ ok: true, revoked });
}
