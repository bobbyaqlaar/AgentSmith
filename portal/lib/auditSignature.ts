// portal/lib/auditSignature.ts — the audit log's tamper-evidence layer.
//
// Split out of auditLog.ts so the signing and verification of an event can be
// exercised without a database. That is not a testing convenience: the audit
// log makes two independent claims, and they are enforced by different things.
//
//   * TAMPER-EVIDENCE — a mutated event no longer verifies. Pure crypto over
//     the event's own fields; needs nothing but a key. This module.
//   * APPEND-ONLY — UPDATE and DELETE are refused. Enforced by triggers in
//     db/schema.sql, and only a live database can demonstrate it. auditLog.ts.
//
// While both lived in one module, importing it to check a signature also
// imported the connection pool, so the half that needs no infrastructure could
// not be verified without infrastructure — and SEC-AUDIT-001 was declared a
// gap on exactly that basis.
//
// Signing here is the SECOND layer, deliberately: it catches tampering by
// someone with direct database access who disables the trigger (SPECS.md §30).

import { createHmac, timingSafeEqual } from "node:crypto";

// The event catalog, mirroring lib/isolation.ts: one runtime array, the type
// derived from it, one guard. It was previously a bare type union here plus a
// hand-kept VALID_TYPES array in BOTH audit routes — three places to edit to
// add an event, and missing one gave a value that type-checks, is accepted by
// /api/audit/append and rejected by /api/audit, or the reverse.
export const AUDIT_EVENT_TYPES = [
  "hook_bypass",
  "hitl_promotion",
  "config_change",
  "tenant_created",
] as const;

export type AuditEventType = (typeof AUDIT_EVENT_TYPES)[number];

export function isValidAuditEventType(value: unknown): value is AuditEventType {
  return typeof value === "string" && (AUDIT_EVENT_TYPES as readonly string[]).includes(value);
}

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

// Exported so tamper-evidence can be tested against the real signer. The
// alternative was for the test to recompute the HMAC itself, which is a second
// implementation of the thing under test: it would keep passing if this one
// changed its canonical field order, and a signature scheme that silently stops
// matching what it used to produce is the defect the audit log exists to expose.
export function signEvent(e: Omit<AuditEvent, "signature">): string {
  return createHmac("sha256", hmacKey()).update(canonicalPayload(e)).digest("hex");
}

export function verifySignature(e: AuditEvent): boolean {
  const expected = signEvent(e);
  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(e.signature, "hex");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}
