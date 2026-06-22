// portal/lib/auditLog.ts — immutable, signed audit log (SPECS.md §30).
//
// Every event is HMAC-SHA256 signed over its own fields using
// AUDIT_LOG_HMAC_KEY (a server-side secret, never sent to clients). The
// `audit_log` table also has DB-level triggers blocking UPDATE/DELETE
// (db/schema.sql) — the signature is the second layer, catching tampering
// even by someone with direct database access who disables the trigger.

import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { getPool } from "./db";

export type AuditEventType = "hook_bypass" | "hitl_promotion" | "config_change" | "tenant_created";

export interface AuditEvent {
  eventId: string;
  timestamp: string;
  eventType: AuditEventType;
  actorId: string;
  tenantId: string | null;
  details: Record<string, unknown>;
  signature: string;
}

function hmacKey(): string {
  const key = process.env.AUDIT_LOG_HMAC_KEY;
  if (!key) {
    throw new Error(
      "AUDIT_LOG_HMAC_KEY is not set — the audit log refuses to write or verify events without it " +
        "(an unsigned audit log provides no tamper-detection, see SPECS.md §30)."
    );
  }
  return key;
}

// Deterministic JSON serialisation with recursively sorted object keys.
//
// This matters because `details` round-trips through Postgres JSONB, which
// does NOT preserve key insertion order — a value written as {a:1, b:2} can
// come back as {b:2, a:1}. Plain JSON.stringify is key-order-sensitive, so
// without this, re-signing a freshly-read (but completely untouched) row
// would produce a different signature than the one computed at write time —
// a false "tampering" positive on every legitimate multi-key `details`
// object. Sorting keys recursively makes the signature stable regardless of
// storage-layer reordering.
function canonicalStringify(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalStringify).join(",")}]`;
  }
  const keys = Object.keys(value as Record<string, unknown>).sort();
  const entries = keys.map((k) => `${JSON.stringify(k)}:${canonicalStringify((value as Record<string, unknown>)[k])}`);
  return `{${entries.join(",")}}`;
}

// Canonical field order matters — both signing and verification must hash
// the exact same byte sequence, or every signature mismatches.
function canonicalPayload(e: Omit<AuditEvent, "signature">): string {
  return canonicalStringify({
    eventId: e.eventId,
    timestamp: e.timestamp,
    eventType: e.eventType,
    actorId: e.actorId,
    tenantId: e.tenantId,
    details: e.details,
  });
}

function sign(e: Omit<AuditEvent, "signature">): string {
  return createHmac("sha256", hmacKey()).update(canonicalPayload(e)).digest("hex");
}

export function verifySignature(e: AuditEvent): boolean {
  const expected = sign(e);
  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(e.signature, "hex");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

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
  const signature = sign(unsigned);
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
