// portal/test/dlqCostWidget.test.ts — DLQ triage state transitions, cost
// period math, and widget-token scoping (TestCoverageReview-2026-07-21
// gap 6). Requires a real Postgres with db/schema.sql applied — same
// "test against real infra, not mocks" pattern as auditLog.test.ts; runs
// in the portal CI job's test:db lane.
//
// dlq_entries and llm_gateway_budget are owned by runtime/dead_letter.py
// and runtime/llm_gateway.py respectively (not db/schema.sql) — this test
// creates them with the same DDL those owners use, exactly as a worker
// would have.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//      node --experimental-strip-types test/dlqCostWidget.test.ts

import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { getPool } from "../lib/db.ts";
import { getTenantCost, getAllTenantsCurrentSpend } from "../lib/cost.ts";
import {
  getDLQStatus,
  listDLQEntries,
  getDlqEntry,
  discardDlqEntry,
  replayDlqEntry,
  ReplayNotConfiguredError,
  ReplayWebhookError,
} from "../lib/dlq.ts";
import {
  createWidgetToken,
  resolveWidgetToken,
  revokeWidgetToken,
  revokeWidgetTokensForTenant,
} from "../lib/widgetTokens.ts";
import { upsertTenant } from "../lib/tenants.ts";

if (!process.env.DATABASE_URL) {
  console.error("DATABASE_URL is required for this test (run npm run db:migrate against it first).");
  process.exit(1);
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

const pool = getPool();
const t = Date.now();
const tenantA = `dcw-a-${t}`;
const tenantB = `dcw-b-${t}`;

// The "table not created yet" paths must run before this test creates the
// python-owned tables — drop them so a re-run against a dirty DB is stable.
await pool.query(`DROP TABLE IF EXISTS dlq_entries`);
await pool.query(`DROP TABLE IF EXISTS llm_gateway_budget`);

await upsertTenant({ tenantId: tenantA, name: tenantA, budgetCapUsd: 100 });
await upsertTenant({
  tenantId: tenantB,
  name: tenantB,
  replayWebhookUrl: "https://worker.example.test/replay",
  replayWebhookSecret: "test-webhook-secret",
});

// ── Not-wired paths (python-owned tables absent) ─────────────────────────────

await test("getDLQStatus reports not-wired before any worker has migrated", async () => {
  const status = await getDLQStatus();
  assert.equal(status.wired, false);
  assert.deepEqual(status.pendingByTenant, {});
  assert.deepEqual(await listDLQEntries(tenantA), []);
  assert.equal(await getDlqEntry("nope"), null);
});

await test("getTenantCost degrades to zeros (cap still from tenants) without budget table", async () => {
  const cost = await getTenantCost(tenantA);
  assert.equal(cost.spentUsd, 0);
  assert.equal(cost.cap, 100);
  assert.deepEqual(cost.history, []);
  assert.deepEqual(await getAllTenantsCurrentSpend(), {});
});

// ── Create the python-owned tables (same DDL as their owners) ────────────────

await pool.query(`
  CREATE TABLE IF NOT EXISTS llm_gateway_budget (
    tenant_id TEXT NOT NULL,
    period TEXT NOT NULL,
    spent_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, period)
  )`);
await pool.query(`
  CREATE TABLE IF NOT EXISTS dlq_entries (
    task_id      TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    payload      JSONB NOT NULL,
    error        TEXT NOT NULL,
    reason       TEXT,
    workflow_id  TEXT,
    gate_id      TEXT,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'replayed', 'discarded')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    replayed_at  TIMESTAMPTZ,
    discarded_at TIMESTAMPTZ
  )`);

// ── Cost period math ─────────────────────────────────────────────────────────

const currentPeriod = new Date().toISOString().slice(0, 7);

await test("getTenantCost picks the current period and returns ascending history", async () => {
  await pool.query(
    `INSERT INTO llm_gateway_budget (tenant_id, period, spent_usd) VALUES
     ($1, '2024-01', 9.5), ($1, $2, 12.25), ($1, '2024-02', 3.0)`,
    [tenantA, currentPeriod]
  );
  const cost = await getTenantCost(tenantA);
  assert.equal(cost.spentUsd, 12.25);
  assert.equal(cost.cap, 100);
  assert.deepEqual(
    cost.history.map((h) => h.period),
    ["2024-01", "2024-02", currentPeriod] // DESC query, then reversed
  );
});

await test("getAllTenantsCurrentSpend only counts the current period", async () => {
  await pool.query(
    `INSERT INTO llm_gateway_budget (tenant_id, period, spent_usd) VALUES ($1, $2, 1.5)`,
    [tenantB, currentPeriod]
  );
  const spend = await getAllTenantsCurrentSpend();
  assert.equal(spend[tenantA], 12.25);
  assert.equal(spend[tenantB], 1.5);
});

// ── DLQ triage ───────────────────────────────────────────────────────────────

await test("wired status counts only pending entries per tenant", async () => {
  await pool.query(
    `INSERT INTO dlq_entries (task_id, tenant_id, payload, error, reason, workflow_id, gate_id) VALUES
     ('task-1', $1, '{"step": 1}', 'boom', 'validation_rejected', 'wf-1', 'gate-a'),
     ('task-2', $1, '{"step": 2}', 'boom2', NULL, NULL, NULL),
     ('task-3', $2, '{"step": 3}', 'boom3', NULL, 'wf-3', NULL)`,
    [tenantA, tenantB]
  );
  const status = await getDLQStatus();
  assert.equal(status.wired, true);
  assert.equal(status.pendingByTenant[tenantA], 2);
  assert.equal(status.pendingByTenant[tenantB], 1);
});

await test("listDLQEntries is tenant-scoped; getDlqEntry derives tenant from task alone", async () => {
  const entries = await listDLQEntries(tenantA);
  assert.deepEqual(entries.map((e) => e.taskId).sort(), ["task-1", "task-2"]);
  const entry = await getDlqEntry("task-3");
  assert.equal(entry?.tenantId, tenantB); // never client-supplied
  assert.equal(entry?.workflowId, "wf-3");
});

await test("discard transitions pending→discarded exactly once", async () => {
  assert.equal(await discardDlqEntry("task-2"), true);
  assert.equal(await discardDlqEntry("task-2"), false); // already discarded
  const { rows } = await pool.query(`SELECT status, discarded_at FROM dlq_entries WHERE task_id = 'task-2'`);
  assert.equal(rows[0].status, "discarded");
  assert.notEqual(rows[0].discarded_at, null);
  assert.equal((await getDLQStatus()).pendingByTenant[tenantA], 1);
});

await test("replay without a configured webhook raises ReplayNotConfiguredError", async () => {
  await assert.rejects(
    () => replayDlqEntry(tenantA, "task-1", { step: 1 }),
    ReplayNotConfiguredError
  );
});

await test("replay HMAC-signs the edited payload for the tenant's own webhook", async () => {
  const captured: { url?: string; body?: string; sig?: string } = {};
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async (url: any, init: any) => {
    captured.url = String(url);
    captured.body = init.body;
    captured.sig = init.headers["X-Replay-Signature"];
    return { ok: true, status: 200, text: async () => "" };
  }) as any;
  try {
    await replayDlqEntry(tenantB, "task-3", { step: 3, fixed: true });
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.equal(captured.url, "https://worker.example.test/replay");
  assert.deepEqual(JSON.parse(captured.body!), { taskId: "task-3", payload: { step: 3, fixed: true } });
  const expected =
    "sha256=" + createHmac("sha256", "test-webhook-secret").update(captured.body!).digest("hex");
  assert.equal(captured.sig, expected);
});

await test("a non-2xx webhook response raises ReplayWebhookError (DB stays pending)", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = (async () => ({ ok: false, status: 500, text: async () => "worker down" })) as any;
  try {
    await assert.rejects(() => replayDlqEntry(tenantB, "task-3", {}), ReplayWebhookError);
  } finally {
    globalThis.fetch = realFetch;
  }
  const entry = await getDlqEntry("task-3");
  assert.equal(entry?.status, "pending"); // only the tenant's receiver marks replayed
});

// ── Widget token scoping ─────────────────────────────────────────────────────

await test("mint→resolve round-trip; only the hash is persisted", async () => {
  const token = await createWidgetToken(tenantA);
  assert.equal(await resolveWidgetToken(token), tenantA);
  const { rows } = await pool.query(`SELECT token_hash FROM widget_tokens WHERE tenant_id = $1`, [tenantA]);
  assert.ok(rows.every((r) => r.token_hash !== token)); // plaintext never stored
  assert.equal(await resolveWidgetToken(""), null);
  assert.equal(await resolveWidgetToken("not-a-real-token"), null);
});

await test("a token resolves only its own tenant, and revocation is immediate", async () => {
  const tokenB = await createWidgetToken(tenantB);
  assert.equal(await resolveWidgetToken(tokenB), tenantB); // never tenantA
  await revokeWidgetToken(tokenB);
  assert.equal(await resolveWidgetToken(tokenB), null);
});

await test("revokeWidgetTokensForTenant kills every active token, counts them, spares other tenants", async () => {
  const t1 = await createWidgetToken(tenantA);
  const t2 = await createWidgetToken(tenantA);
  const other = await createWidgetToken(tenantB);
  const revoked = await revokeWidgetTokensForTenant(tenantA);
  assert.ok(revoked >= 2); // t1, t2 (+ any earlier active token for tenantA)
  assert.equal(await resolveWidgetToken(t1), null);
  assert.equal(await resolveWidgetToken(t2), null);
  assert.equal(await resolveWidgetToken(other), tenantB); // untouched
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
