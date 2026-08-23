// POST /api/audit/append — append a signed audit event (SPECS.md §30).
//
// Called from CLI/CI contexts that can't carry the dashboard's basic-auth
// credentials: ai-tenant-init (tenant_created), ai-tenant-promote
// (hitl_promotion), install-ai-stack.sh's break-glass bypass path
// (hook_bypass), scripts/promote-learning.py (hitl_promotion), etc.
// Authenticates via its own bearer token, like /api/sync/history.
//
// Body: { eventType, actorId, tenantId?, details? }

import { NextResponse } from "next/server";
import { requireBearer } from "@/lib/bearerAuth";
import { appendAuditEvent, AUDIT_EVENT_TYPES, isValidAuditEventType } from "@/lib/auditLog";


export async function POST(request: Request) {
  const denied = requireBearer(request, { envVar: "AUDIT_LOG_WRITE_TOKEN", purpose: "audit ingestion" });
  if (denied) return denied;


  const body = await request.json().catch(() => null);
  if (!isValidAuditEventType(body?.eventType)) {
    return NextResponse.json({ error: `eventType must be one of: ${AUDIT_EVENT_TYPES.join(", ")}` }, { status: 400 });
  }
  if (!body?.actorId) {
    return NextResponse.json({ error: "actorId is required" }, { status: 400 });
  }

  try {
    const event = await appendAuditEvent({
      eventType: body.eventType,
      actorId: body.actorId,
      tenantId: body.tenantId ?? null,
      details: body.details ?? {},
    });
    return NextResponse.json({ ok: true, eventId: event.eventId });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
