// POST /api/runs/ingest — best-effort run-status updates from
// runtime/llm_gateway.py (Product_Archive.md P2a). Same auth shape as
// /api/sync/history: a single shared bearer token
// (OPS_PORTAL_SYNC_TOKEN — reused, not a second token, since both are
// "a production worker pushing operational data to the shared portal").
//
// Body shape:
//   { tenantId, runId, workflowId?, status, traceId?, errorSummary? }
//
// Upserts by run_id — the gateway calls this once at run start
// (status: "running") and again at run end (status: "success"/"degraded"/
// "failed"), both referencing the same runId.

import { NextResponse } from "next/server";
import { requireBearer } from "@/lib/bearerAuth";
import { upsertAgentRun } from "@/lib/runStatus";
import { getTenant, upsertTenant } from "@/lib/tenants";

const VALID_STATUSES = ["running", "success", "degraded", "failed"];

export async function POST(request: Request) {
  const denied = requireBearer(request, { envVar: "OPS_PORTAL_SYNC_TOKEN", purpose: "run ingestion" });
  if (denied) return denied;


  const body = await request.json().catch(() => null);
  if (!body?.tenantId || !body?.runId || !body?.status) {
    return NextResponse.json({ error: "tenantId, runId, and status are required" }, { status: 400 });
  }
  if (!VALID_STATUSES.includes(body.status)) {
    return NextResponse.json({ error: `status must be one of: ${VALID_STATUSES.join(", ")}` }, { status: 400 });
  }

  if (!(await getTenant(body.tenantId))) {
    // Same auto-registration convenience as /api/sync/history.
    await upsertTenant({ tenantId: body.tenantId, name: body.tenantId });
  }

  await upsertAgentRun({
    runId: body.runId,
    tenantId: body.tenantId,
    workflowId: body.workflowId ?? null,
    status: body.status,
    traceId: body.traceId ?? null,
    errorSummary: body.errorSummary ?? null,
  });

  return NextResponse.json({ ok: true });
}
