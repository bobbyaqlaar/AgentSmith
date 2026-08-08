// portal/test/auditSignature.test.ts — HMAC tamper-evidence, no database.
//
// SEC-AUDIT-001's evidence. Split out of auditLog.test.ts, which needs a live
// Postgres and exits at import time without DATABASE_URL — so the control that
// depended on it could never run in CI, and was declared a gap for that reason.
//
// The split is along a real seam, not a convenient one. The audit log makes two
// separate claims:
//
//   1. TAMPER-EVIDENCE — a mutated event no longer verifies. Pure crypto over
//      the event's own fields. Provable here, in CI, on every commit.
//   2. APPEND-ONLY — UPDATE and DELETE are refused. That is enforced by
//      database triggers (db/schema.sql), and nothing running without a
//      database can honestly assert it. It stays in auditLog.test.ts and is
//      claimed by SEC-AUDIT-002 as a live control.
//
// Collapsing those two into one green tick was the thing to avoid: it would
// have reported "audit log verified" while the half that actually stops a
// deletion went unchecked.

import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

process.env.AUDIT_LOG_HMAC_KEY ??= "test-key-not-a-secret";

const { signEvent, verifySignature } = await import("../lib/auditSignature.ts");

type Event = Parameters<typeof verifySignature>[0];

function event(overrides: Partial<Event> = {}): Event {
  const unsigned = {
    eventId: randomUUID(),
    timestamp: new Date().toISOString(),
    eventType: "config_change" as const,
    actorId: "alice",
    tenantId: "acme",
    details: { setting: "moderation", from: "off", to: "required" },
    ...overrides,
  };
  return { ...unsigned, signature: signEvent(unsigned) } as Event;
}

let failures = 0;
function check(name: string, fn: () => void): void {
  try {
    fn();
    console.log(`  ok  ${name}`);
  } catch (err) {
    failures += 1;
    console.error(`  FAIL ${name}\n       ${(err as Error).message}`);
  }
}

check("a freshly signed event verifies", () => {
  assert.equal(verifySignature(event()), true);
});

// Each mutation is a field an attacker would actually want to change: who did
// it, which tenant it touched, what it changed, and when.
for (const field of ["actorId", "tenantId", "eventType", "timestamp"] as const) {
  check(`tampering with ${field} breaks the signature`, () => {
    const e = event();
    const mutated = { ...e, [field]: field === "eventType" ? "hook_bypass" : "mallory" };
    assert.equal(verifySignature(mutated as Event), false);
  });
}

check("tampering inside details breaks the signature", () => {
  const e = event();
  const mutated = { ...e, details: { ...e.details, to: "off" } };
  assert.equal(verifySignature(mutated as Event), false);
});

// The reason canonicalStringify sorts keys recursively: Postgres JSONB does not
// preserve insertion order, so an untouched row can come back with its details
// keys reordered. If the signature were order-sensitive, every legitimate
// multi-key event would read as tampered — a false positive on every row, which
// would train whoever reads the report to ignore it.
check("details key order does not affect the signature", () => {
  const base = { eventId: randomUUID(), timestamp: new Date().toISOString(),
    eventType: "config_change" as const, actorId: "alice", tenantId: "acme" };
  const a = signEvent({ ...base, details: { x: 1, y: { p: 2, q: 3 } } });
  const b = signEvent({ ...base, details: { y: { q: 3, p: 2 }, x: 1 } });
  assert.equal(a, b);
});

check("a truncated signature is rejected rather than throwing", () => {
  const e = event();
  assert.equal(verifySignature({ ...e, signature: e.signature.slice(0, 16) }), false);
});

check("a non-hex signature is rejected rather than throwing", () => {
  const e = event();
  assert.equal(verifySignature({ ...e, signature: "zz".repeat(32) }), false);
});

// Without a key there is no tamper-detection at all, so refusing loudly beats
// signing with a default: a log that silently signs with a well-known key reads
// as protected and is not.
check("a missing HMAC key refuses rather than signing with a default", () => {
  const saved = process.env.AUDIT_LOG_HMAC_KEY;
  delete process.env.AUDIT_LOG_HMAC_KEY;
  try {
    assert.throws(() => signEvent({
      eventId: "x", timestamp: "t", eventType: "config_change",
      actorId: "a", tenantId: null, details: {},
    }), /AUDIT_LOG_HMAC_KEY/);
  } finally {
    process.env.AUDIT_LOG_HMAC_KEY = saved;
  }
});

console.log(failures === 0 ? "audit signature: all checks passed" : `audit signature: ${failures} failed`);
process.exit(failures === 0 ? 0 : 1);
