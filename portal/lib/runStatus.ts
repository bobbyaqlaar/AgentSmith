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
//   - any other entry as the latest activity              -> "success"
//   - NO entries at all, and no agent_runs row            -> "unknown"
// That last line used to say "success" too, which is how a tenant whose
// pipeline had never run once showed a green dot in its own product.
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
import { isSafeHttpUrl } from "./safeUrl";

/** The statuses a worker can REPORT, and the exact set `agent_runs.status`
 *  CHECKs in db/schema.sql. One catalog, the type derived from it — the shape
 *  lib/isolation.ts and lib/authz.ts's ROLES already use. It was written out
 *  three times: this union, `VALID_STATUSES` in the ingest route, and the SQL
 *  constraint. Adding one to the union alone gives a value that type-checks,
 *  is rejected by the route; adding it to both gives one Postgres rejects with
 *  a 500 at the moment a real run reports it. */
export const AGENT_RUN_STATUSES = ["running", "success", "degraded", "failed"] as const;

export type AgentRunStatus = (typeof AGENT_RUN_STATUSES)[number];

/** What the widget is told. `unknown` is portal-side only — nothing writes it
 *  to the database, it means "nothing has been recorded for this tenant". */
export type RunStatus = AgentRunStatus | "unknown";

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
  status: AgentRunStatus;
  traceId: string | null;
  errorSummary: string | null;
  // null = the provider reported no usage (a streamed call has none in v1),
  // which is a different fact from 0. Kept nullable end to end so a consumer
  // summing spend can show a gap instead of a confident undercount.
  inputTokens?: number | null;
  outputTokens?: number | null;
  costUsd?: number | null;
}

export async function upsertAgentRun(input: UpsertAgentRunInput): Promise<void> {
  const finished = input.status !== "running";
  await getPool().query(
    `INSERT INTO agent_runs (run_id, tenant_id, workflow_id, status, trace_id, error_summary,
                             input_tokens, output_tokens, cost_usd, finished_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, ${finished ? "now()" : "NULL"})
     ON CONFLICT (run_id) DO UPDATE SET
       -- A late 'running' must not un-finish a run. The gateway's two POSTs
       -- are best-effort HTTP: a retried or reordered START can arrive after
       -- the END, and a bare EXCLUDED.status put the row back to 'running'
       -- with finished_at still set. Verified against Postgres: the widget
       -- then reported a completed run as running, permanently, and in a
       -- multi-call group that row masked a genuine 'failed'.
       --
       -- Every neighbouring column already had this guard, each with a comment
       -- saying a later heartbeat must not blank what was recorded. Status was
       -- the one column that did not get it.
       status = CASE
                  WHEN EXCLUDED.status = 'running' AND agent_runs.finished_at IS NOT NULL
                    THEN agent_runs.status
                  ELSE EXCLUDED.status
                END,
       trace_id = COALESCE(EXCLUDED.trace_id, agent_runs.trace_id),
       error_summary = EXCLUDED.error_summary,
       -- COALESCE, like trace_id above: the gateway upserts once at run START
       -- with no usage yet and again at the end with it. A bare EXCLUDED would
       -- let a later 'running' heartbeat blank a figure already recorded.
       input_tokens = COALESCE(EXCLUDED.input_tokens, agent_runs.input_tokens),
       output_tokens = COALESCE(EXCLUDED.output_tokens, agent_runs.output_tokens),
       cost_usd = COALESCE(EXCLUDED.cost_usd, agent_runs.cost_usd),
       finished_at = ${finished ? "now()" : "agent_runs.finished_at"}`,
    [
      input.runId,
      input.tenantId,
      input.workflowId,
      input.status,
      input.traceId,
      input.errorSummary,
      input.inputTokens ?? null,
      input.outputTokens ?? null,
      input.costUsd ?? null,
    ]
  );
}

interface AgentRunRow {
  run_id: string;
  status: AgentRunStatus;
  started_at: string;
  finished_at: string | null;
  trace_id: string | null;
  error_summary: string | null;
}

const TERMINAL_SEVERITY: Record<string, number> = { failed: 3, degraded: 2, success: 1 };

/** Severity of a status, and 0 for anything not terminal.
 *
 *  Total on purpose. The reduce below compared `TERMINAL_SEVERITY[r.status]`
 *  directly, so a row whose status is not in that map — 'running' on a row that
 *  also has finished_at, which the upsert above used to produce — yielded
 *  `undefined`, and `3 > undefined` is false. The accumulator won every
 *  comparison, so one contradictory row hid a real 'failed' from the whole
 *  group. Rows in that state can still exist from before the upsert was fixed,
 *  and a collapse that depends on the writer being correct is not a collapse. */
function severity(status: string): number {
  return TERMINAL_SEVERITY[status] ?? 0;
}

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
  const worst = rows.reduce((acc, r) => (severity(r.status) > severity(acc.status) ? r : acc));
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
  // NOTHING RECORDED IS NOT SUCCESS. A tenant with no agent_runs rows and no
  // history entries — a pipeline that has never run, or a worker that has
  // never reached this portal — used to report "success", and the In-App
  // Widget embedded in that tenant's own product showed a green dot to their
  // users. `unknown` was already in this union and already had a grey label
  // and colour in templates/in-app-widget/widget.js; the only thing missing
  // was anything that produced it.
  //
  // "success" is still the answer when entries EXIST and the latest is benign.
  // That is a measurement. An empty table is not.
  let status: RunStatus = latest ? "success" : "unknown";
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
    // Scheme-checked HERE, not only at the render sites. This value is served
    // to the In-App Widget, which puts it in an `href` inside the TENANT's own
    // product — so a `phoenix_base_url` of `javascript:…` would be XSS in a
    // customer's page, not in an operator's dashboard. POST /api/tenants
    // validates on the way in now, but rows written before that still hold
    // anything, and a deployed widget never updates. The server is the only
    // place that protects both.
    traceUrl:
      tenant?.phoenixBaseUrl && isSafeHttpUrl(tenant.phoenixBaseUrl)
        ? tenantTraceUrl(tenant.phoenixBaseUrl)
        : null,
  };
}
