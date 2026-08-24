// POST /api/sync/history — ingestion endpoint for .agent-history.log entries.
//
// Called from cd-staging.yml / cd-production.yml (or manually via
// ai-stack-check) once per tenant CD run, pushing any MAJOR/CRITICAL entries
// since the last sync. Authenticates via Authorization: Bearer
// $OPS_PORTAL_SYNC_TOKEN — a single shared secret stored as a GitHub
// Environment secret in each tenant repo (SPECS.md §17, §19, §26).
//
// Body shape:
//   { "tenantId": "acme", "entries": [...], "budgetCapUsd"?: number,
//     "replayWebhookUrl"?: string, "replayWebhookSecret"?: string }
//
// budgetCapUsd (Product_Archive.md P2b) is optional — when
// scripts/sync-portal-history.py finds gateway.budget_cap_usd in this
// tenant's .agenticframework/tenant.yaml, it's included on every sync call
// (not just the first) so the portal's displayed cap stays current if the
// tenant repo's tenant.yaml changes. This is a display value only — it
// does not enforce anything; the real enforcement is
// runtime/llm_gateway.py's own AGENT_MONTHLY_USD_CAP on the worker.
//
// replayWebhookUrl/replayWebhookSecret (HITL/DLQ redesign) are the same
// pattern — synced from this tenant's own tenant.yaml's hitl.* section —
// but unlike budgetCapUsd they're not just a display value: the Ops
// Portal's DLQ "Replay with edits" action actually POSTs the human-edited
// payload to this URL, HMAC-signed with this secret, so it must stay
// per-tenant-correct (see portal/lib/dlq.ts's replayDlqEntry()).

import { NextResponse } from "next/server";
import { requireBearer } from "@/lib/bearerAuth";
import { syncHistoryEntries, type SyncEntryInput } from "@/lib/issues";
import { upsertTenant, getTenant } from "@/lib/tenants";
import { portalSpan, withIdentity } from "@/lib/tracing";

export async function POST(request: Request) {
  const denied = requireBearer(request, { envVar: "OPS_PORTAL_SYNC_TOKEN", purpose: "sync ingestion" });
  if (denied) return denied;


  const body = await request.json().catch(() => null);
  if (!body?.tenantId || !Array.isArray(body?.entries)) {
    return NextResponse.json({ error: "tenantId and entries[] are required" }, { status: 400 });
  }

  const tenantId: string = body.tenantId;
  const entries: SyncEntryInput[] = body.entries;
  const budgetCapUsd: number | null =
    typeof body.budgetCapUsd === "number" && Number.isFinite(body.budgetCapUsd) ? body.budgetCapUsd : null;
  const replayWebhookUrl: string | null = typeof body.replayWebhookUrl === "string" ? body.replayWebhookUrl : null;
  const replayWebhookSecret: string | null =
    typeof body.replayWebhookSecret === "string" ? body.replayWebhookSecret : null;
  const hasUpdate = budgetCapUsd !== null || replayWebhookUrl !== null || replayWebhookSecret !== null;

  const existingTenant = await getTenant(tenantId);
  if (!existingTenant) {
    // Auto-register on first sync so a tenant doesn't need a separate
    // provisioning step before its CD pipeline can push history.
    await upsertTenant({ tenantId, name: tenantId, budgetCapUsd, replayWebhookUrl, replayWebhookSecret });
  } else if (hasUpdate) {
    // upsertTenant's UPDATE sets name unconditionally (not COALESCE) — pass
    // the tenant's own current name back, not tenantId, or this would
    // silently clobber a real display name (e.g. "Acme") to the raw id on
    // every sync that happens to carry any of these optional fields.
    await upsertTenant({ tenantId, name: existingTenant.name, budgetCapUsd, replayWebhookUrl, replayWebhookSecret });
  }

  // Both counts, because they are different numbers: syncHistoryEntries
  // deduplicates by entryId before it writes, so received > written is a
  // tenant pushing the same entry twice in one batch — visible here and
  // nowhere else, since the upsert makes it harmless and silent.
  const written = await withIdentity({ tenantId }, () =>
    portalSpan(
      "portal.sync.history",
      { attributes: { "sync.entries_received": entries.length } },
      async (span) => {
        const count = await syncHistoryEntries(tenantId, entries);
        span.setAttribute("sync.entries_written", count);
        return count;
      },
    ),
  );
  return NextResponse.json({ ok: true, written });
}
