// POST /api/runs/ingest — best-effort run-status updates from
// runtime/llm_gateway.py (Product_Archive.md P2a). Same auth shape as
// /api/sync/history: a single shared bearer token
// (OPS_PORTAL_SYNC_TOKEN — reused, not a second token, since both are
// "a production worker pushing operational data to the shared portal").
//
// Body shape:
//   { tenantId, runId, workflowId?, status, traceId?, errorSummary?,
//     inputTokens?, outputTokens?, costUsd? }
//
// Usage fields are nullable and omitted rather than zeroed when the provider
// reported none — a streamed call has no usage in v1, which is not the same
// fact as a call that used zero tokens.
//
// Upserts by run_id — the gateway calls this once at run start
// (status: "running") and again at run end (status: "success"/"degraded"/
// "failed"), both referencing the same runId.

import { NextResponse } from "next/server";
import { requireBearer } from "@/lib/bearerAuth";
import { upsertAgentRun } from "@/lib/runStatus";
import { getTenant, upsertTenant } from "@/lib/tenants";

const VALID_STATUSES = ["running", "success", "degraded", "failed"];

/** Numbers only. A non-numeric body field becomes null — recorded as "not
 *  reported" — rather than being coerced to 0, which would read as a real
 *  measurement of zero. */
function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** The 32-hex trace id out of a W3C `traceparent`, or null.
 *
 *  Parsed rather than handed to an OTel SDK on purpose: the portal is not
 *  instrumented, and correlating the row to the trace does not require it to
 *  be. Shape is `00-<32 hex trace>-<16 hex span>-<2 hex flags>`; an all-zero
 *  trace id is the invalid one the spec reserves, and is rejected so it cannot
 *  be stored as though it were real. */
function traceIdFromHeader(request: Request): string | null {
  const header = request.headers.get("traceparent");
  if (!header) return null;
  const parts = header.split("-");
  if (parts.length < 4 || parts[0] !== "00") return null;
  const traceId = parts[1];
  if (!/^[0-9a-f]{32}$/.test(traceId) || /^0+$/.test(traceId)) return null;
  return traceId;
}

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
    // Body first, then the W3C traceparent header the worker now injects.
    // agent_runs.trace_id was NULL for every run ever recorded — the gateway
    // accepted a trace_id argument that none of its nine call sites passed —
    // so the portal's "view trace" link had nothing to link to.
    traceId: body.traceId ?? traceIdFromHeader(request) ?? null,
    errorSummary: body.errorSummary ?? null,
    inputTokens: numberOrNull(body.inputTokens),
    outputTokens: numberOrNull(body.outputTokens),
    costUsd: numberOrNull(body.costUsd),
  });

  return NextResponse.json({ ok: true });
}
