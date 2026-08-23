// portal/lib/auditLog.ts — immutable, signed audit log (SPECS.md §30).
//
// The persistence half. Signing and verification live in ./auditSignature so
// they can be exercised without a database — see that file for why the seam is
// there. Re-exported below so existing importers of this module are unchanged.
//
// The `audit_log` table has DB-level triggers blocking UPDATE/DELETE
// (db/schema.sql); the HMAC signature is the second layer, catching tampering
// even by someone with direct database access who disables the trigger.

import { randomUUID } from "node:crypto";
import { getPool } from "./db";
import { signEvent, verifySignature, type AuditEvent, type AuditEventType } from "./auditSignature";

export { signEvent, verifySignature };
export type { AuditEvent, AuditEventType };
// Re-exported alongside the type so a caller validating an event needs one
// import, not two — the routes already import appendAuditEvent/listAuditEvents
// from here.
export { AUDIT_EVENT_TYPES, isValidAuditEventType } from "./auditSignature";

export interface AppendAuditEventInput {
  eventType: AuditEventType;
  actorId: string;
  tenantId?: string | null;
  details?: Record<string, unknown>;
}

export async function appendAuditEvent(input: AppendAuditEventInput): Promise<AuditEvent> {
  const unsigned: Omit<AuditEvent, "signature"> = {
    eventId: randomUUID(),
    timestamp: new Date().toISOString(),
    eventType: input.eventType,
    actorId: input.actorId,
    tenantId: input.tenantId ?? null,
    details: input.details ?? {},
  };
  const signature = signEvent(unsigned);
  const event: AuditEvent = { ...unsigned, signature };

  await getPool().query(
    `INSERT INTO audit_log (event_id, "timestamp", event_type, actor_id, tenant_id, details, signature)
     VALUES ($1, $2, $3, $4, $5, $6, $7)`,
    [event.eventId, event.timestamp, event.eventType, event.actorId, event.tenantId, JSON.stringify(event.details), event.signature]
  );

  return event;
}

export interface AuditEventWithVerification extends AuditEvent {
  verified: boolean;
}

export async function listAuditEvents(opts: {
  tenantId?: string;
  eventType?: AuditEventType;
  limit?: number;
} = {}): Promise<AuditEventWithVerification[]> {
  const conditions: string[] = [];
  const params: unknown[] = [];
  if (opts.tenantId) {
    params.push(opts.tenantId);
    conditions.push(`tenant_id = $${params.length}`);
  }
  if (opts.eventType) {
    params.push(opts.eventType);
    conditions.push(`event_type = $${params.length}`);
  }
  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  params.push(opts.limit ?? 200);

  const { rows } = await getPool().query(
    `SELECT event_id, "timestamp", event_type, actor_id, tenant_id, details, signature
     FROM audit_log ${where}
     ORDER BY "timestamp" DESC
     LIMIT $${params.length}`,
    params
  );

  return rows.map((r) => {
    const event: AuditEvent = {
      eventId: r.event_id,
      timestamp: r.timestamp instanceof Date ? r.timestamp.toISOString() : r.timestamp,
      eventType: r.event_type,
      actorId: r.actor_id,
      tenantId: r.tenant_id,
      details: r.details,
      signature: r.signature,
    };
    return { ...event, verified: verifySignature(event) };
  });
}
