// POST /api/sync/history — ingestion endpoint for .agent-history.log entries.
//
// Called from cd-staging.yml / cd-production.yml (or manually via
// ai-stack-check) once per tenant CD run, pushing any MAJOR/CRITICAL entries
// since the last sync. Authenticates via Authorization: Bearer
// $OPS_PORTAL_SYNC_TOKEN — a single shared secret stored as a GitHub
// Environment secret in each tenant repo (SPECS.md §17, §19, §26).
//
// Body shape:
//   { "tenantId": "acme", "entries": [{ entryId, level, event, timestamp, hitlResolved?, raw }] }

import { NextResponse } from "next/server";
import { syncHistoryEntries, type SyncEntryInput } from "@/lib/issues";
import { upsertTenant, getTenant } from "@/lib/tenants";

export async function POST(request: Request) {
  const token = process.env.OPS_PORTAL_SYNC_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "OPS_PORTAL_SYNC_TOKEN is not configured on the portal — sync ingestion is disabled." },
      { status: 503 }
    );
  }

  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${token}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const body = await request.json().catch(() => null);
  if (!body?.tenantId || !Array.isArray(body?.entries)) {
    return NextResponse.json({ error: "tenantId and entries[] are required" }, { status: 400 });
  }

  const tenantId: string = body.tenantId;
  const entries: SyncEntryInput[] = body.entries;

  if (!(await getTenant(tenantId))) {
    // Auto-register on first sync so a tenant doesn't need a separate
    // provisioning step before its CD pipeline can push history.
    await upsertTenant({ tenantId, name: tenantId });
  }

  const written = await syncHistoryEntries(tenantId, entries);
  return NextResponse.json({ ok: true, written });
}
