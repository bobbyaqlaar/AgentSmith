// GET /api/audit — list audit events (basic auth, dashboard). Each event is
// returned with `verified: boolean` — the result of recomputing its
// HMAC-SHA256 signature server-side. A `false` here means the row was
// altered after being written (or AUDIT_LOG_HMAC_KEY was rotated without
// re-signing history — rotate carefully).

import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { listAuditEvents, type AuditEventType } from "@/lib/auditLog";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, canAdmin, getAccessFromHeaderValues } from "@/lib/authz";

const VALID_TYPES: AuditEventType[] = ["hook_bypass", "hitl_promotion", "config_change", "tenant_created"];

export async function GET(request: Request) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  // Audit events span hook-bypass/config-change actions that aren't always
  // tenant-scoped (tenant_id is nullable) — only admins get to see the feed.
  if (!canAdmin(access)) {
    return NextResponse.json({ error: "admin role required" }, { status: 403 });
  }

  const url = new URL(request.url);
  const tenantId = url.searchParams.get("tenantId") ?? undefined;
  if (tenantId && !canAccessTenant(access, tenantId)) {
    return NextResponse.json({ error: `forbidden: no access to tenant ${tenantId}` }, { status: 403 });
  }
  const eventTypeParam = url.searchParams.get("eventType");
  const eventType = eventTypeParam && VALID_TYPES.includes(eventTypeParam as AuditEventType)
    ? (eventTypeParam as AuditEventType)
    : undefined;
  const limit = Number(url.searchParams.get("limit")) || undefined;

  try {
    const events = await listAuditEvents({ tenantId, eventType, limit });
    return NextResponse.json({ events });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
