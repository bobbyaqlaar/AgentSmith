// POST /api/sync/history — ingestion endpoint for .agent-history.log entries.
//
// Called from cd-staging.yml / cd-production.yml (or manually via
// agentsmith check) once per tenant CD run, pushing any MAJOR/CRITICAL entries
// since the last sync. Authenticates via Authorization: Bearer
// $OPS_PORTAL_SYNC_TOKEN — a single shared secret stored as a GitHub
// Environment secret in each tenant repo (docs/DESIGN.md › CI/CD via GitHub Actions, Structured Agent History Log, Federated Observability).
//
// Body shape:
//   { "tenantId": "acme", "entries": [...], "budgetCapUsd"?: number,
//     "replayWebhookUrl"?: ignored, "replayWebhookSecret"?: ignored }
//
// DEPRECATED with its sender, scripts/sync-portal-history.py (retired): a
// worker reports its settings by the Ops contract (/api/ops/ingest,
// contract/ops/v1). Kept, with the shared token, until an operator unsets
// OPS_PORTAL_SYNC_TOKEN; it no longer stores a replay secret.
//
// budgetCapUsd (docs/PRODUCT_ARCHIVE.md P2b) is optional — when
// the sender found gateway.budget_cap_usd in this
// tenant's .agenticframework/tenant.yaml, it's included on every sync call
// (not just the first) so the portal's displayed cap stays current if the
// tenant repo's tenant.yaml changes. This is a display value only — it
// does not enforce anything; the real enforcement is
// runtime/llm_gateway.py's own AGENT_MONTHLY_USD_CAP on the worker.
//
// replayWebhookUrl/replayWebhookSecret in a body are ignored: where a
// person's fix is sent, and the key it is signed with, are the app's own Ops
// settings and the portal's issued key (contract/ops/v1) — never something a
// caller holding the shared token can set for any tenant.

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
  // Same scheme check as POST /api/tenants — this is the OTHER writer of the
  // URL the portal later POSTs a replayed payload to, and a validation that
  // lands at one of two writers is not a validation.
  // Nor a replay webhook URL. Under the one token every tenant shares, this
  // route would let any holder point another tenant's replays — a person's fix,
  // signed with that tenant's key — at an address of its choosing. The URL is
  // the app's own to declare, by the Ops contract with its own Ops token.
  const replayWebhookUrl = null;
  // A replay secret in the body is never stored. The replay key is the
  // portal's to issue (Administration › Apps, contract/ops/v1): this shared-
  // token route could otherwise overwrite the issued key with whatever a
  // caller sends, and the secret it carried came from a committed tenant.yaml.
  const hasUpdate = budgetCapUsd !== null || replayWebhookUrl !== null;

  const existingTenant = await getTenant(tenantId);
  if (!existingTenant) {
    // Auto-register on first sync so a tenant doesn't need a separate
    // provisioning step before its CD pipeline can push history.
    await upsertTenant({ tenantId, name: tenantId, budgetCapUsd, replayWebhookUrl });
  } else if (hasUpdate) {
    // upsertTenant's UPDATE sets name unconditionally (not COALESCE) — pass
    // the tenant's own current name back, not tenantId, or this would
    // silently clobber a real display name (e.g. "Acme") to the raw id on
    // every sync that happens to carry any of these optional fields.
    await upsertTenant({ tenantId, name: existingTenant.name, budgetCapUsd, replayWebhookUrl });
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
