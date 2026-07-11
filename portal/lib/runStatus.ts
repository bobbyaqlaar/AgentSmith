// portal/lib/runStatus.ts — "last agent run status" for the In-App Widget.
//
// Prefers the agent_runs table (Product_Archive.md P2a) — populated by
// runtime/llm_gateway.py's best-effort POST /api/runs/ingest at run
// start/end — when a row exists for the tenant; this is what makes
// "running" a reachable status for the first time. Falls back to deriving
// a status from the most recent synced .agent-history.log entry when no
// agent_runs row exists yet (e.g. a tenant whose workers predate this
// table, or OPS_PORTAL_URL was never configured on the worker side):
//   - an unresolved CRITICAL entry as the latest activity -> "failed"
//   - an unresolved MAJOR entry as the latest activity    -> "degraded"
//   - anything else (or no entries at all)                -> "success"
// The fallback path still can't derive "running" — that gap only closes
// once a real agent_runs row exists.
//
// One agent_runs row = one runtime/llm_gateway.py `complete()` call, not
// one workflow run — a tenant app with multiple agents/LLM calls per
// workflow (the expected shape this framework builds toward, not just the
// single-call oil-price example) reports one row per call, all sharing
// `workflow_id` as a grouping key. getWidgetStatus aggregates every row
// for the tenant's most recent workflow (or, if workflow_id is null, just
// that one ungrouped row) into a single status: "running" if ANY call in
// that group hasn't finished yet (covers sequential AND concurrent/
// fan-out calls), else the worst terminal status among them.

import { getPool } from "./db";
import { getTenant } from "./tenants";
import { tenantTraceUrl } from "./phoenix";

export type RunStatus = "running" | "success" | "degraded" | "failed" | "unknown";

export interface WidgetStatus {
  tenantId: string;
  status: RunStatus;
  lastEventAt: string | null;
  errorSummary: string | null;
  traceUrl: string | null;
}

export interface UpsertAgentRunInput {
  runId: string;
  tenantId: string;
  workflowId: string | null;
  status: "running" | "success" | "degraded" | "failed";
  traceId: string | null;
  errorSummary: string | null;
}

export async function upsertAgentRun(input: UpsertAgentRunInput): Promise<void> {
  const finished = input.status !== "running";
  await getPool().query(
    `INSERT INTO agent_runs (run_id, tenant_id, workflow_id, status, trace_id, error_summary, finished_at)
     VALUES ($1, $2, $3, $4, $5, $6, ${finished ? "now()" : "NULL"})
     ON CONFLICT (run_id) DO UPDATE SET
       status = EXCLUDED.status,
       trace_id = COALESCE(EXCLUDED.trace_id, agent_runs.trace_id),
       error_summary = EXCLUDED.error_summary,
       finished_at = ${finished ? "now()" : "agent_runs.finished_at"}`,
    [input.runId, input.tenantId, input.workflowId, input.status, input.traceId, input.errorSummary]
  );
}

interface AgentRunRow {
  run_id: string;
  status: "running" | "success" | "degraded" | "failed";
  started_at: string;
  finished_at: string | null;
  trace_id: string | null;
  error_summary: string | null;
}

const TERMINAL_SEVERITY: Record<string, number> = { failed: 3, degraded: 2, success: 1 };

// Returns every agent_runs row that belongs to the same logical run as the
// tenant's most recently started call — same workflow_id when one was
// reported, or just that single row when it wasn't (an ungrouped/ad-hoc
// gateway call never gets merged with anything else by workflow_id=NULL,
// since NULL never equals NULL in SQL — each is its own one-row group).
async function getLatestRunGroup(tenantId: string): Promise<AgentRunRow[]> {
  const { rows: latest } = await getPool().query(
    `SELECT run_id, workflow_id FROM agent_runs
     WHERE tenant_id = $1 ORDER BY started_at DESC LIMIT 1`,
    [tenantId]
  );
  if (latest.length === 0) return [];

  const { run_id, workflow_id } = latest[0];
  const { rows } = await getPool().query(
    workflow_id !== null
      ? `SELECT run_id, status, started_at, finished_at, trace_id, error_summary
         FROM agent_runs WHERE tenant_id = $1 AND workflow_id = $2
         ORDER BY started_at DESC`
      : `SELECT run_id, status, started_at, finished_at, trace_id, error_summary
         FROM agent_runs WHERE tenant_id = $1 AND run_id = $2
         ORDER BY started_at DESC`,
    [tenantId, workflow_id !== null ? workflow_id : run_id]
  );
  return rows;
}

// Collapses a run group into one widget-facing status:
//   - any still-open call (finished_at IS NULL) -> "running", regardless
//     of how many calls in the group already finished (a fan-out where
//     2 of 3 parallel LLM calls are done and 1 is still in flight is
//     still "running" overall)
//   - otherwise -> the worst terminal status across the group
//     (failed > degraded > success) — one failed call in a multi-call
//     workflow should not be masked by a later call's "success"
function collapseRunGroup(rows: AgentRunRow[]) {
  const openRow = rows.find((r) => r.finished_at === null);
  if (openRow) {
    return { status: openRow.status, lastEventAt: openRow.started_at, errorSummary: openRow.error_summary };
  }
  const worst = rows.reduce((acc, r) => (TERMINAL_SEVERITY[r.status] > TERMINAL_SEVERITY[acc.status] ? r : acc));
  return { status: worst.status, lastEventAt: worst.finished_at ?? worst.started_at, errorSummary: worst.error_summary };
}

async function getStatusFromHistoryLog(tenantId: string) {
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

  return { status, lastEventAt: latest?.timestamp ?? null, errorSummary };
}

export async function getWidgetStatus(tenantId: string): Promise<WidgetStatus> {
  const tenant = await getTenant(tenantId);
  const runGroup = await getLatestRunGroup(tenantId);

  const { status, lastEventAt, errorSummary } =
    runGroup.length > 0 ? collapseRunGroup(runGroup) : await getStatusFromHistoryLog(tenantId);

  return {
    tenantId,
    status,
    lastEventAt,
    errorSummary,
    traceUrl: tenant?.phoenixBaseUrl ? tenantTraceUrl(tenant.phoenixBaseUrl) : null,
  };
}
