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
import { appendAuditEvent, type AuditEventType } from "@/lib/auditLog";

const VALID_TYPES: AuditEventType[] = ["hook_bypass", "hitl_promotion", "config_change", "tenant_created"];

export async function POST(request: Request) {
  const token = process.env.AUDIT_LOG_WRITE_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "AUDIT_LOG_WRITE_TOKEN is not configured on the portal — audit ingestion is disabled." },
      { status: 503 }
    );
  }

  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${token}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => null);
  if (!body?.eventType || !VALID_TYPES.includes(body.eventType)) {
    return NextResponse.json({ error: `eventType must be one of: ${VALID_TYPES.join(", ")}` }, { status: 400 });
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
