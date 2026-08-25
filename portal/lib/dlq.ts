// portal/lib/dlq.ts — dead-letter queue depth + per-entry triage for the
// Ops Portal (Product_Archive.md HITL/DLQ redesign).
//
// runtime/dead_letter.py's DeadLetterQueue is Postgres-backed and creates
// `dlq_entries` itself (CREATE TABLE IF NOT EXISTS) the first time a worker
// constructs one against DATABASE_URL — not via this portal's own
// migration (db/schema.sql deliberately excludes it; see that file's
// comment). Until at least one worker has done that, the table won't exist
// yet and callers get an explicit "not wired" result instead of fabricated
// zeros — that's a genuine "no worker has run against this DB" signal, not
// a placeholder for an unimplemented backend.
//
// "Replay with edits" (replayDlqEntry) does NOT call into Python/Temporal
// directly — the portal has no Temporal client and isn't meant to gain
// one (dead_letter.py's replay_handler is deliberately engine-agnostic).
// Instead it HMAC-signs the edited payload and POSTs it to the entry's
// OWN tenant's replay_webhook_url (see runtime/replay_webhook_server.py)
// — per-tenant by construction, so a human-in-the-loop fix always reaches
// the specific team running that tenant's worker, never a shared,
// cross-tenant endpoint.

import { createHmac } from "node:crypto";
import { capped, type CappedList } from "./cappedList";
import { getPool, tableExists, columnExists } from "./db";
import { getReplayWebhookConfig } from "./tenants";

export interface DLQStatus {
  wired: boolean;
  pendingByTenant: Record<string, number>;
}

export interface DLQEntry {
  taskId: string;
  tenantId: string;
  payload: unknown;
  error: string;
  reason: string | null;
  workflowId: string | null;
  gateId: string | null;
  status: "pending" | "replayed" | "discarded";
  createdAt: string;
}

export async function getDLQStatus(): Promise<DLQStatus> {
  const hasTable = await tableExists("dlq_entries");
  if (!hasTable) {
    return { wired: false, pendingByTenant: {} };
  }
  const { rows } = await getPool().query(
    `SELECT tenant_id, count(*) AS n FROM dlq_entries WHERE status = 'pending' GROUP BY tenant_id`
  );
  const pendingByTenant: Record<string, number> = {};
  for (const r of rows) pendingByTenant[r.tenant_id] = Number(r.n);
  return { wired: true, pendingByTenant };
}

async function hasReasonColumns(): Promise<boolean> {
  // All three were added together (runtime/dead_letter.py) — checking one
  // is representative of the others.
  return columnExists("dlq_entries", "reason");
}

/**
 * Pending entries for a tenant, or NULL when the table does not exist yet.
 *
 * Null rather than `[]` for the reason getDLQStatus already carries `wired`,
 * and the reason getSuggestedPromotions in lib/promotions.ts returns null: the
 * tenant DLQ page rendered "No pending DLQ entries for this tenant" — a health
 * claim — from a database that has never had a worker connect to it. The index
 * page one click earlier said "Not wired" correctly. Same fact, two answers,
 * and the reassuring one was on the page an operator actually reads.
 */
const DLQ_LIMIT = 100;

export async function listDLQEntries(
  tenantId: string,
  status: string = "pending",
): Promise<CappedList<DLQEntry> | null> {
  if (!(await tableExists("dlq_entries"))) return null;
  const hasReason = await hasReasonColumns();
  const where = `WHERE tenant_id = $1 AND status = $2`;
  // The count comes back with the rows for the same reason it does in
  // lib/issues.ts: the page showed at most 100 entries and said nothing about
  // it, while the index page one click earlier showed the real total.
  const [{ rows }, { rows: countRows }] = await Promise.all([
    getPool().query(
      hasReason
        ? `SELECT task_id, tenant_id, payload, error, reason, workflow_id, gate_id, status, created_at
           FROM dlq_entries ${where} ORDER BY created_at DESC LIMIT ${DLQ_LIMIT}`
        : `SELECT task_id, tenant_id, payload, error, status, created_at
           FROM dlq_entries ${where} ORDER BY created_at DESC LIMIT ${DLQ_LIMIT}`,
      [tenantId, status]
    ),
    getPool().query(`SELECT count(*)::int AS n FROM dlq_entries ${where}`, [tenantId, status]),
  ]);
  const entries = rows.map((r) => ({
    taskId: r.task_id,
    tenantId: r.tenant_id,
    payload: r.payload,
    error: r.error,
    reason: r.reason ?? null,
    workflowId: r.workflow_id ?? null,
    gateId: r.gate_id ?? null,
    status: r.status,
    createdAt: r.created_at,
  }));
  return capped(entries, countRows[0]?.n ?? entries.length, DLQ_LIMIT);
}

// Looks up an entry by task_id alone, no tenant_id required from the
// caller — the API routes use this to derive which tenant's webhook to
// hit, never trusting a client-supplied tenantId (that would let a
// malicious/buggy client redirect a replay to a DIFFERENT tenant's
// webhook than the one the entry actually belongs to).
export async function getDlqEntry(taskId: string): Promise<DLQEntry | null> {
  if (!(await tableExists("dlq_entries"))) return null;
  const hasReason = await hasReasonColumns();
  const { rows } = await getPool().query(
    hasReason
      ? `SELECT task_id, tenant_id, payload, error, reason, workflow_id, gate_id, status, created_at
         FROM dlq_entries WHERE task_id = $1`
      : `SELECT task_id, tenant_id, payload, error, status, created_at
         FROM dlq_entries WHERE task_id = $1`,
    [taskId]
  );
  const r = rows[0];
  if (!r) return null;
  return {
    taskId: r.task_id,
    tenantId: r.tenant_id,
    payload: r.payload,
    error: r.error,
    reason: r.reason ?? null,
    workflowId: r.workflow_id ?? null,
    gateId: r.gate_id ?? null,
    status: r.status,
    createdAt: r.created_at,
  };
}

export class ReplayNotConfiguredError extends Error {}
export class ReplayWebhookError extends Error {}
/** The receiver refused because the entry is no longer pending (HTTP 409).
 *  Separated from ReplayWebhookError because nothing failed — reporting
 *  "replay failed" for a replay that already happened sends an operator
 *  looking for a problem that does not exist. */
export class ReplayAlreadyResolvedError extends Error {}

/**
 * Sends the (possibly human-edited) payload to this entry's tenant's own
 * replay_webhook_url, HMAC-signed with that tenant's replay_webhook_secret.
 * Does NOT update dlq_entries itself — the tenant's receiver
 * (runtime/replay_webhook_server.py) is responsible for calling
 * DeadLetterQueue.replay(taskId, override_payload=...) once it has
 * actually signaled the live workflow, so the DB only reflects "replayed"
 * once a real resume attempt happened, not just "the portal tried to
 * notify someone."
 */
export async function replayDlqEntry(tenantId: string, taskId: string, editedPayload: unknown): Promise<void> {
  const config = await getReplayWebhookConfig(tenantId);
  if (!config) {
    throw new ReplayNotConfiguredError(
      `Tenant '${tenantId}' has no replay_webhook_url/secret configured — see OPERATIONS.md "Wire your platform" for HITL/DLQ.`
    );
  }
  const body = JSON.stringify({ taskId, payload: editedPayload });
  const signature = "sha256=" + createHmac("sha256", config.secret).update(body).digest("hex");

  const resp = await fetch(config.url, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Replay-Signature": signature },
    body,
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    if (resp.status === 409) {
      // runtime/dead_letter.py claims the row before signalling, so a second
      // replay — a retry, a double-click, a resent webhook — is refused rather
      // than re-running the workflow. That refusal is the system working.
      throw new ReplayAlreadyResolvedError(
        "This entry is no longer pending — it was already replayed or discarded. Nothing was re-sent.",
      );
    }
    throw new ReplayWebhookError(`Tenant replay webhook returned ${resp.status}: ${text}`);
  }
}

/**
 * Discard is safe to do directly from the portal (unlike replay) — it
 * never needs to resume a live workflow, just mark the entry resolved.
 */
export async function discardDlqEntry(taskId: string): Promise<boolean> {
  // Its siblings all check first. Unreachable today — the routes look the
  // entry up before calling this, and that lookup returns null on an absent
  // table — but "unreachable because of what another module happens to do
  // first" is not a property this module can rely on.
  if (!(await tableExists("dlq_entries"))) return false;
  const { rowCount } = await getPool().query(
    `UPDATE dlq_entries SET status = 'discarded', discarded_at = now() WHERE task_id = $1 AND status = 'pending'`,
    [taskId]
  );
  return (rowCount ?? 0) > 0;
}
