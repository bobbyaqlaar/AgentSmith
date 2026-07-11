// POST /api/dlq/:taskId/replay — "Replay with edits" (Product_Archive.md
// HITL/DLQ redesign). Body: { payload: <edited JSON> }.
//
// tenantId is ALWAYS derived from the DLQ entry's own row, never trusted
// from the request body — otherwise a client could redirect a replay to
// a different tenant's webhook than the one the entry actually belongs to.

import { NextResponse } from "next/server";
import { headers } from "next/headers";
import { getDlqEntry, replayDlqEntry, ReplayNotConfiguredError, ReplayWebhookError } from "@/lib/dlq";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAccessTenant, canWrite, getAccessFromHeaderValues } from "@/lib/authz";

export async function POST(request: Request, { params }: { params: { taskId: string } }) {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
  if (!canWrite(access)) {
    return NextResponse.json({ error: "operator or admin role required to replay DLQ entries" }, { status: 403 });
  }

  const entry = await getDlqEntry(params.taskId);
  if (!entry) {
    return NextResponse.json({ error: `Unknown DLQ entry ${params.taskId}` }, { status: 404 });
  }
  // Treat out-of-scope identically to nonexistent — same posture as the
  // tenant detail page (a 403 would itself leak "this entry exists").
  if (!canAccessTenant(access, entry.tenantId)) {
    return NextResponse.json({ error: `Unknown DLQ entry ${params.taskId}` }, { status: 404 });
  }
  if (entry.status !== "pending") {
    return NextResponse.json({ error: `Entry ${params.taskId} is already ${entry.status}` }, { status: 409 });
  }

  const body = await request.json().catch(() => null);
  if (!body || !("payload" in body)) {
    return NextResponse.json({ error: "payload is required" }, { status: 400 });
  }

  try {
    await replayDlqEntry(entry.tenantId, entry.taskId, body.payload);
  } catch (err) {
    if (err instanceof ReplayNotConfiguredError) {
      return NextResponse.json({ error: err.message }, { status: 503 });
    }
    if (err instanceof ReplayWebhookError) {
      return NextResponse.json({ error: err.message }, { status: 502 });
    }
    return NextResponse.json({ error: err instanceof Error ? err.message : "replay failed" }, { status: 500 });
  }

  // resumable: false flags an entry with no workflow_id/gate_id — e.g.
  // one from the older run_with_hitl_gate's terminal dead-letter, not
  // run_with_recoverable_step. The webhook call above still happened
  // (the tenant's receiver decides what to do — restart fresh, etc.),
  // but the reference receiver (runtime/replay_webhook_server.py) just
  // logs a warning and no-ops on a live signal when these are missing —
  // "ok":true alone would otherwise read as "resumed," which isn't
  // necessarily true here.
  return NextResponse.json({ ok: true, resumable: Boolean(entry.workflowId && entry.gateId) });
}
