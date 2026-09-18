// GET /api/audit — list audit events (basic auth, dashboard). Each event is
// returned with `verified: boolean` — the result of recomputing its
// HMAC-SHA256 signature server-side. A `false` here means the row was
// altered after being written (or AUDIT_LOG_HMAC_KEY was rotated without
// re-signing history — rotate carefully).

import { NextResponse } from "next/server";
import { listAuditEvents, isValidAuditEventType } from "@/lib/auditLog";
import { can } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";


export async function GET(request: Request) {
  const access = currentAccess();
  // Audit events span hook-bypass/config-change actions that aren't always
  // tenant-scoped (tenant_id is nullable) — only admins get to see the feed.
  if (!can(access, "admin.audit")) {
    return NextResponse.json({ error: "Administrator role required" }, { status: 403 });
  }

  const url = new URL(request.url);
  const tenantId = url.searchParams.get("tenantId") ?? undefined;
  if (tenantId && !can(access, "admin.audit", tenantId)) {
    return NextResponse.json({ error: `forbidden: no access to tenant ${tenantId}` }, { status: 403 });
  }
  const eventTypeParam = url.searchParams.get("eventType");
  // No cast: isValidAuditEventType is a type guard, so the true branch is
  // already narrowed. The old `as AuditEventType` would have silently accepted
  // a widened value if the guard ever stopped matching the catalog.
  const eventType = isValidAuditEventType(eventTypeParam) ? eventTypeParam : undefined;
  const limit = Number(url.searchParams.get("limit")) || undefined;

  try {
    const events = await listAuditEvents({ tenantId, eventType, limit });
    return NextResponse.json({ events });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
