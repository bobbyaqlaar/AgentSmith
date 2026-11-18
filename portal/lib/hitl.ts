// portal/lib/hitl.ts — human decisions on compliance-profile gates, and the stop
// control. Both reach the app over its signed webhook (contract/ops/v1).

import { appendAuditEvent } from "./auditLog";
import { getPool, withTransaction } from "./db";
import { mayDecide } from "./complianceState";
import { replaySignatureHeaders } from "./dlq";
import { getReplayWebhookConfig } from "./tenants";

export interface PendingGate {
  tenantId: string;
  recordId: number;
  gateId: string;
  workflowId: string;
  action: string;
  input: unknown;
  inputSha256: string;
  requestedBy: string | null;
  createdAt: string;
}

export class HitlError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function toPending(row: Record<string, unknown>): PendingGate {
  const p = row.payload as Record<string, unknown>;
  return {
    tenantId: row.tenant_id as string,
    recordId: Number(row.record_id),
    gateId: String(p.gate_id),
    workflowId: String(p.workflow_id),
    action: String(p.action),
    input: p.input,
    inputSha256: String(p.input_sha256),
    requestedBy: (p.requested_by as string | null) ?? null,
    createdAt: (row.created_at as Date).toISOString(),
  };
}

// A timeout hides only the requests made before it: a gate asked again after one
// timed out is a new request, and reaches the queue (the 4.1.0 release review, R21).
export const PENDING = `SELECT r.* FROM compliance_records r
  WHERE r.record_kind = 'hitl_pending' AND NOT EXISTS (
    SELECT 1 FROM hitl_decisions d WHERE d.tenant_id = r.tenant_id AND d.record_id = r.record_id)
  AND NOT EXISTS (
    SELECT 1 FROM compliance_records t WHERE t.tenant_id = r.tenant_id AND t.record_kind = 'hitl_timeout'
      AND t.record_id > r.record_id
      AND t.payload->>'workflow_id' = r.payload->>'workflow_id' AND t.payload->>'gate_id' = r.payload->>'gate_id')`;

export async function listPending(tenantIds: string[]): Promise<PendingGate[]> {
  const { rows } = await getPool().query(`${PENDING} AND r.tenant_id = ANY($1) ORDER BY r.created_at`, [tenantIds]);
  return rows.map(toPending);
}

export async function getPending(tenantId: string, recordId: number): Promise<PendingGate | null> {
  const { rows } = await getPool().query(`${PENDING} AND r.tenant_id = $1 AND r.record_id = $2`, [tenantId, recordId]);
  return rows[0] ? toPending(rows[0]) : null;
}

async function postSigned(tenantId: string, message: Record<string, unknown>): Promise<void> {
  const config = await getReplayWebhookConfig(tenantId);
  if (!config) throw new HitlError(503, "this app declares no webhook, or has no replay key issued");
  const body = JSON.stringify({ schema: 1, tenant_id: tenantId, ...message });
  const resp = await fetch(config.url, {
    method: "POST",
    headers: { "content-type": "application/json", ...replaySignatureHeaders(config.secret, body) },
    body,
    redirect: "manual",
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok) throw new HitlError(502, `the app's webhook answered ${resp.status || "with a redirect"}`);
}

/** What the app receives: the decision, the input digest the reviewer was shown, and
 *  the request it answers. Two requests can show one input, so the digest alone could
 *  not say which one (the 4.1.0 review's second pass, P2-R14). */
export function decisionMessage(
  gate: Pick<PendingGate, "recordId" | "gateId" | "workflowId" | "inputSha256">,
  input: { approved: boolean; actor: string; role: string; rationale: string },
  decidedAt: Date = new Date(),
): Record<string, unknown> {
  return {
    gate_id: gate.gateId, workflow_id: gate.workflowId, approved: input.approved, actor: input.actor, role: input.role,
    rationale: input.rationale, payload_sha256: gate.inputSha256, decided_at: decidedAt.toISOString(),
    request_record_id: gate.recordId,
  };
}

/** The decision, its audit line and its delivery stand or fall together. */
export async function decideGate(input: {
  tenantId: string; recordId: number; approved: boolean; actor: string; role: string; rationale: string;
}): Promise<void> {
  const gate = await getPending(input.tenantId, input.recordId);
  if (!gate) throw new HitlError(404, "this gate is not waiting for a decision");
  if (!mayDecide(input.actor, gate.requestedBy)) throw new HitlError(403, "a person does not decide their own request");
  await withTransaction("hitl_decide", async (client) => {
    await client.query(
      `INSERT INTO hitl_decisions (tenant_id, record_id, approved, actor, rationale) VALUES ($1,$2,$3,$4,$5)`,
      [input.tenantId, input.recordId, input.approved, input.actor, input.rationale],
    );
    await appendAuditEvent(
      { eventType: "hitl_decision", actorId: input.actor, tenantId: input.tenantId,
        details: { recordId: input.recordId, gateId: gate.gateId, workflowId: gate.workflowId, approved: input.approved, inputSha256: gate.inputSha256 } },
      client,
    );
    await postSigned(input.tenantId, { decision: decisionMessage(gate, input) });
  });
}

export interface StopRecord { action: string; actor: string; reason: string; receivedAt: Date }
export interface PortalStop { action: string; actor: string; at: Date }
export interface StopState {
  stopped: boolean; actor: string | null; reason: string | null;
  /** Whether the app has recorded any stop or resume for the whole app. */
  recorded: boolean;
  /** A stop or resume sent from the portal that the app has not recorded yet. */
  sent: { action: string; actor: string } | null;
}

/** The app's newest record decides whether it is stopped, whether the stop came from the
 *  portal or from `agentsmith ops stop` at a terminal. A portal action newer than that
 *  record is shown as sent, not as done (the 4.1.0 review's second pass, P2-R19). Both
 *  times are the portal's own clock: when the record arrived, and when the action was sent. */
export function stopState(record: StopRecord | null, portal: PortalStop | null): StopState {
  const sent = portal && (!record || portal.at.getTime() > record.receivedAt.getTime())
    ? { action: portal.action, actor: portal.actor } : null;
  if (!record) return { stopped: false, actor: null, reason: null, recorded: false, sent };
  return { stopped: record.action === "stop", actor: record.actor, reason: record.reason, recorded: true, sent };
}

/** Whether the app is stopped, from its own forwarded `stop_control` records. */
export async function appStopState(tenantId: string): Promise<StopState> {
  const pool = getPool();
  const [records, actions] = await Promise.all([
    pool.query(
      `SELECT payload, received_at FROM compliance_records WHERE tenant_id = $1 AND record_kind = 'stop_control'
         AND payload->>'scope' = '*' ORDER BY record_id DESC LIMIT 1`, [tenantId]),
    pool.query(
      `SELECT actor_id, details, "timestamp" FROM audit_log WHERE tenant_id = $1 AND event_type = 'stop_control'
         AND details->>'scope' = '*' ORDER BY "timestamp" DESC LIMIT 1`, [tenantId]),
  ]);
  const r = records.rows[0], a = actions.rows[0];
  return stopState(
    r ? { action: String(r.payload.action), actor: String(r.payload.actor ?? ""), reason: String(r.payload.reason ?? ""),
          receivedAt: new Date(r.received_at) } : null,
    a ? { action: String(a.details.action), actor: String(a.actor_id), at: new Date(a.timestamp) } : null,
  );
}

type StopInput = { tenantId: string; action: "stop" | "resume"; scope: string; reason: string; actor: string };
interface StopDeps {
  withTransaction: (name: string, work: (client: never) => Promise<void>) => Promise<unknown>;
  appendAuditEvent: (event: Parameters<typeof appendAuditEvent>[0], client: never) => Promise<unknown>;
  postSigned: (tenantId: string, message: Record<string, unknown>) => Promise<void>;
}

/** The audit line and the delivery stand or fall together, as a decision does: a stop the
 *  app refused was audited as given before (P2-R19). */
export async function sendStopControl(deps: StopDeps, input: StopInput): Promise<void> {
  await deps.withTransaction("stop_control", async (client) => {
    await deps.appendAuditEvent({ eventType: "stop_control", actorId: input.actor, tenantId: input.tenantId,
                                  details: { action: input.action, scope: input.scope, reason: input.reason } }, client);
    await deps.postSigned(input.tenantId, { stop: { action: input.action, scope: input.scope, reason: input.reason, actor: input.actor } });
  });
}

export async function stopControl(input: StopInput): Promise<void> {
  await sendStopControl({ withTransaction, appendAuditEvent, postSigned } as unknown as StopDeps, input);
}
