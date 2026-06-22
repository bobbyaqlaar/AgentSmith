// portal/lib/runStatus.ts — best-effort "last agent run status" for the
// In-App Widget.
//
// HONEST LIMITATION: there is no dedicated "run" table yet — runtime/worker.py
// and scripts/multi_agent_system.py don't emit explicit run-start/run-end
// events to the portal. This derives a status from the most recent synced
// .agent-history.log entry instead:
//   - an unresolved CRITICAL entry as the latest activity -> "failed"
//   - an unresolved MAJOR entry as the latest activity    -> "degraded"
//   - anything else (or no entries at all)                -> "success"
// "running" is not derivable from this data source and is never returned.
// A real run-status table is a documented follow-up (see templates/in-app-widget/README.md).

import { getPool } from "./db";
import { getTenant } from "./tenants";
import { tenantTraceUrl } from "./phoenix";

export type RunStatus = "success" | "degraded" | "failed" | "unknown";

export interface WidgetStatus {
  tenantId: string;
  status: RunStatus;
  lastEventAt: string | null;
  errorSummary: string | null;
  traceUrl: string | null;
}

export async function getWidgetStatus(tenantId: string): Promise<WidgetStatus> {
  const tenant = await getTenant(tenantId);
  const { rows } = await getPool().query(
    `SELECT level, event, timestamp, hitl_resolved
     FROM agent_history_entries
     WHERE tenant_id = $1
     ORDER BY timestamp DESC
     LIMIT 1`,
    [tenantId]
  );

  const latest = rows[0];
  let status: RunStatus = "success";
  let errorSummary: string | null = null;

  if (latest && !latest.hitl_resolved) {
    if (latest.level === "CRITICAL") {
      status = "failed";
      errorSummary = latest.event;
    } else if (latest.level === "MAJOR") {
      status = "degraded";
      errorSummary = latest.event;
    }
  }

  return {
    tenantId,
    status,
    lastEventAt: latest?.timestamp ?? null,
    errorSummary,
    traceUrl: tenant?.phoenixBaseUrl ? tenantTraceUrl(tenant.phoenixBaseUrl) : null,
  };
}
