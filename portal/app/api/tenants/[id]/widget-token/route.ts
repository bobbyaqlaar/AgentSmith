// POST /api/tenants/:id/widget-token — mint a new read-only widget token for
// a tenant (SPECS.md §26). Minting requires `operator` or `admin` (an
// operator's day-to-day job includes onboarding a tenant's widget, same
// tier as creating tenants via POST /api/tenants); revoking requires
// `admin` only, since it instantly breaks every live embed for that
// tenant — a more disruptive action than minting a new one. Both also
// require the caller's tenantScope to include this tenant id. Protected
// by the dashboard's basic auth (this route is NOT in middleware's
// exclusion list). The plaintext token is returned exactly once; only its
// hash is persisted — losing it means minting a new one and updating the
// tenant app's embed snippet.

import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { createWidgetToken, revokeWidgetTokensForTenant } from "@/lib/widgetTokens";
import { getTenant } from "@/lib/tenants";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, canAdmin, canWrite, getAccessFromHeaderValues } from "@/lib/authz";

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  if (!canWrite(access)) {
    return NextResponse.json({ error: "operator or admin role required to mint widget tokens" }, { status: 403 });
  }
  if (!canAccessTenant(access, params.id)) {
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
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  if (!canAdmin(access)) {
    return NextResponse.json({ error: "admin role required to revoke widget tokens" }, { status: 403 });
  }
  if (!canAccessTenant(access, params.id)) {
    return NextResponse.json({ error: `Unknown tenant ${params.id}` }, { status: 404 });
  }

  const tenant = await getTenant(params.id);
  if (!tenant) {
    return NextResponse.json({ error: `Unknown tenant ${params.id}` }, { status: 404 });
  }
  const revoked = await revokeWidgetTokensForTenant(params.id);
  return NextResponse.json({ ok: true, revoked });
}
