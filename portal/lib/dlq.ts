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

import { createHmac } from "crypto";
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

export async function listDLQEntries(tenantId: string, status: string = "pending"): Promise<DLQEntry[]> {
  if (!(await tableExists("dlq_entries"))) return [];
  const hasReason = await hasReasonColumns();
  const { rows } = await getPool().query(
    hasReason
      ? `SELECT task_id, tenant_id, payload, error, reason, workflow_id, gate_id, status, created_at
         FROM dlq_entries WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC LIMIT 100`
      : `SELECT task_id, tenant_id, payload, error, status, created_at
         FROM dlq_entries WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC LIMIT 100`,
    [tenantId, status]
  );
  return rows.map((r) => ({
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
    throw new ReplayWebhookError(`Tenant replay webhook returned ${resp.status}: ${text}`);
  }
}

/**
 * Discard is safe to do directly from the portal (unlike replay) — it
 * never needs to resume a live workflow, just mark the entry resolved.
 */
export async function discardDlqEntry(taskId: string): Promise<boolean> {
  const { rowCount } = await getPool().query(
    `UPDATE dlq_entries SET status = 'discarded', discarded_at = now() WHERE task_id = $1 AND status = 'pending'`,
    [taskId]
  );
  return (rowCount ?? 0) > 0;
}
