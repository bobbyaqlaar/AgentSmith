// GET /api/audit/export — the audit log as signed NDJSON, for a SIEM or an
// object store (DESC ISR 6.9.5). Each line keeps its signature, so the copy can
// be verified without this portal. A caller gets the apps it administers;
// events that belong to no app need the permission for every app.

import { listAuditEvents, scopeAuditEvents } from "@/lib/auditLog";
import { appsWith, holdsEverywhere } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { listTenants } from "@/lib/tenants";

const MAX_LINES = 10_000;

export async function GET() {
  const access = await currentAccess();
  const visible = new Set(appsWith(access, "admin.audit", (await listTenants()).map((t) => t.tenantId)));
  if (visible.size === 0) return new Response(JSON.stringify({ error: "Administrator role required" }), { status: 403 });
  const events = scopeAuditEvents(await listAuditEvents({ limit: MAX_LINES }), visible, holdsEverywhere(access, "admin.audit"));
  return new Response(events.map((e) => JSON.stringify(e)).join("\n") + "\n", { headers: { "content-type": "application/x-ndjson" } });
}
