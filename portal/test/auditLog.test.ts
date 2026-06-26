// portal/test/auditLog.test.ts — HMAC sign/verify round-trip and tamper
// detection for the immutable audit log (SPECS.md §30,
// FIXES_AND_CLEANUP.md P3). Requires a real Postgres with db/schema.sql
// applied (npm run db:migrate) — same "test against real infra, not mocks"
// pattern as templates/in-app-widget/test/widget.test.mjs and this
// directory's authz.test.ts.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//      AUDIT_LOG_HMAC_KEY=test-key \
//      node --experimental-strip-types test/auditLog.test.ts

import assert from "node:assert/strict";
import { appendAuditEvent, listAuditEvents, verifySignature, type AuditEvent } from "../lib/auditLog.ts";
import { getPool } from "../lib/db.ts";

if (!process.env.DATABASE_URL) {
  console.error("DATABASE_URL is required for this test (run npm run db:migrate against it first).");
  process.exit(1);
}
if (!process.env.AUDIT_LOG_HMAC_KEY) {
  process.env.AUDIT_LOG_HMAC_KEY = "test-only-hmac-key-not-a-real-secret";
}

let passed = 0;
async function test(name: string, fn: () => Promise<void> | void) {
  try {
    await fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

const tenantId = `audit-test-${Date.now()}`;

// audit_log.tenant_id has a FK constraint against tenants(tenant_id)
// (FIXES_AND_CLEANUP.md 2.4) — a tenant must exist before an audit event
// can reference it.
await getPool().query(
  `INSERT INTO tenants (tenant_id, name) VALUES ($1, $1) ON CONFLICT (tenant_id) DO NOTHING`,
  [tenantId]
);

await test("appendAuditEvent writes a row that verifies as authentic", async () => {
  const event = await appendAuditEvent({
    eventType: "tenant_created",
    actorId: "test-actor",
    tenantId,
    details: { stack: "python-fastapi", isolation: "shared" },
  });
  assert.equal(verifySignature(event), true);
});

await test("listAuditEvents reports verified: true for an untouched row", async () => {
  const events = await listAuditEvents({ tenantId });
  assert.ok(events.length >= 1);
  assert.equal(events[0].verified, true);
});

await test("SECURITY: tampering with details after the fact flips verified to false", async () => {
  await appendAuditEvent({
    eventType: "config_change",
    actorId: "test-actor",
    tenantId,
    details: { action: "framework_upgrade", version: "1.0.0" },
  });

  // Simulate someone with direct DB access editing a row in place — the
  // append-only trigger blocks UPDATE, so go around it the way a real
  // tamperer with superuser access would: disable the trigger, edit, re-enable.
  const pool = getPool();
  await pool.query("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update");
  try {
    await pool.query(
      `UPDATE audit_log SET details = '{"action":"framework_upgrade","version":"9.9.9-tampered"}'::jsonb
       WHERE tenant_id = $1 AND event_type = 'config_change'`,
      [tenantId]
    );
  } finally {
    await pool.query("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update");
  }

  const events = await listAuditEvents({ tenantId, eventType: "config_change" });
  const tampered = events.find((e) => (e.details as { version?: string }).version === "9.9.9-tampered");
  assert.ok(tampered, "expected to find the tampered row");
  assert.equal(tampered!.verified, false, "tampered row was not flagged unverified");
});

await test("the append-only trigger itself blocks a normal UPDATE", async () => {
  const pool = getPool();
  await assert.rejects(
    pool.query(`UPDATE audit_log SET actor_id = 'someone-else' WHERE tenant_id = $1`, [tenantId]),
    /append-only/
  );
});

await test("the append-only trigger itself blocks DELETE", async () => {
  const pool = getPool();
  await assert.rejects(
    pool.query(`DELETE FROM audit_log WHERE tenant_id = $1`, [tenantId]),
    /append-only/
  );
});

await test("canonicalization is stable across Postgres JSONB key reordering", async () => {
  // details written with keys in one order; Postgres JSONB storage does not
  // guarantee preserving that order on read back — verifySignature must
  // still pass regardless (see auditLog.ts's canonicalStringify comment).
  const event = await appendAuditEvent({
    eventType: "hitl_promotion",
    actorId: "test-actor",
    tenantId,
    details: { zebra: 1, alpha: 2, mike: { nested_b: 1, nested_a: 2 } },
  });
  const [reread] = await listAuditEvents({ tenantId, eventType: "hitl_promotion" });
  assert.deepEqual(reread.details, event.details);
  assert.equal(reread.verified, true);
});

await test("a hand-crafted event with a wrong signature fails verifySignature", () => {
  const forged: AuditEvent = {
    eventId: "00000000-0000-0000-0000-000000000000",
    timestamp: new Date().toISOString(),
    eventType: "hook_bypass",
    actorId: "attacker",
    tenantId: null,
    details: {},
    signature: "0".repeat(64),
  };
  assert.equal(verifySignature(forged), false);
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
