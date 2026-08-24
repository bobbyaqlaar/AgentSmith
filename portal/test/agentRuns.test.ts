// portal/test/agentRuns.test.ts — agent_runs upsert, against a real Postgres.
//
// The usage columns went in with no test touching them. CI runs db:migrate, so
// the schema and its ALTERs are exercised, but nothing inserted a row — a typo
// in upsertAgentRun's nine-parameter INSERT would have shipped silently. Same
// "test against real infra, not mocks" pattern as auditLog.test.ts; runs in the
// portal CI job's test:db lane.
//
// The property under test is the one the columns exist for: NULL usage means
// the provider reported none — a streamed call has none in v1 — and 0 means it
// reported zero. Anything that collapses those two makes a spend dashboard
// undercount every streamed run while looking complete.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/agentRuns.test.ts

import assert from "node:assert/strict";
import { getWidgetStatus, upsertAgentRun } from "../lib/runStatus.ts";
import { upsertTenant } from "../lib/tenants.ts";
import { getPool } from "../lib/db.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const TENANT = `test-runs-${Date.now()}`;
let passed = 0;

async function test(name: string, fn: () => Promise<void>) {
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

async function row(runId: string) {
  const { rows } = await getPool().query(
    `SELECT status, input_tokens, output_tokens, cost_usd FROM agent_runs WHERE run_id = $1`,
    [runId]
  );
  assert.equal(rows.length, 1, `expected one row for ${runId}`);
  return rows[0];
}

const base = { tenantId: TENANT, workflowId: null, traceId: null, errorSummary: null };

await upsertTenant({ tenantId: TENANT, name: TENANT });

await test("reported usage is stored", async () => {
  const runId = `${TENANT}-a`;
  await upsertAgentRun({
    ...base, runId, status: "success",
    inputTokens: 1500, outputTokens: 270, costUsd: 0.0123,
  });
  const r = await row(runId);
  assert.equal(r.input_tokens, 1500);
  assert.equal(r.output_tokens, 270);
  assert.equal(Number(r.cost_usd), 0.0123);
});

await test("unreported usage stays NULL, not 0", async () => {
  const runId = `${TENANT}-b`;
  await upsertAgentRun({ ...base, runId, status: "success" });
  const r = await row(runId);
  assert.equal(r.input_tokens, null, "NULL means nobody counted");
  assert.equal(r.output_tokens, null);
  assert.equal(r.cost_usd, null);
});

await test("a genuine zero is stored as 0, not NULL", async () => {
  const runId = `${TENANT}-c`;
  await upsertAgentRun({
    ...base, runId, status: "success", inputTokens: 0, outputTokens: 0, costUsd: 0,
  });
  const r = await row(runId);
  assert.equal(r.input_tokens, 0, "a provider reporting 0 is a measurement");
  assert.equal(Number(r.cost_usd), 0);
});

await test("running → terminal records usage on the second write", async () => {
  // The real sequence: the gateway upserts at run start with no usage yet,
  // then again at the end with it.
  const runId = `${TENANT}-d`;
  await upsertAgentRun({ ...base, runId, status: "running" });
  assert.equal((await row(runId)).input_tokens, null);

  await upsertAgentRun({
    ...base, runId, status: "success", inputTokens: 42, outputTokens: 7, costUsd: 0.001,
  });
  const r = await row(runId);
  assert.equal(r.status, "success");
  assert.equal(r.input_tokens, 42);
});

await test("a later write without usage does not blank what was recorded", async () => {
  // Why the upsert COALESCEs instead of taking EXCLUDED outright. A retry or a
  // late heartbeat carrying no usage must not erase a figure already stored.
  const runId = `${TENANT}-e`;
  await upsertAgentRun({
    ...base, runId, status: "success", inputTokens: 99, outputTokens: 11, costUsd: 0.5,
  });
  await upsertAgentRun({ ...base, runId, status: "degraded" });
  const r = await row(runId);
  assert.equal(r.status, "degraded", "status still takes the newest value");
  assert.equal(r.input_tokens, 99, "usage survived a write that carried none");
  assert.equal(Number(r.cost_usd), 0.5);
});

// ── TENANT's teardown. Anything below this point must bring its own tenant:
//    a test appended here that reuses TENANT fails on a foreign key, which is
//    a confusing way to learn about a cleanup twenty lines up.
await getPool().query(`DELETE FROM agent_runs WHERE tenant_id = $1`, [TENANT]);
await getPool().query(`DELETE FROM tenants WHERE tenant_id = $1`, [TENANT]);

// ── Out-of-order heartbeats ─────────────────────────────────────────────────
//
// Their own tenant. TENANT's rows are torn down mid-file (just above), which
// is a boundary an appended test cannot see — the same shape as the
// `getPool().end()` that used to sit there and killed anything added after it.
// A test that owns its fixture does not care where the teardown is.

const REORDER = `test-reorder-${Date.now()}`;
await upsertTenant({ tenantId: REORDER, name: REORDER });
const reorderBase = { ...base, tenantId: REORDER };

await test("a late 'running' heartbeat does not un-finish a completed run", async () => {
  // The gateway's start/end POSTs are best-effort HTTP; a retried or reordered
  // START can land after the END. Without the guard the row went back to
  // 'running' with finished_at still set, and the widget reported a finished
  // run as running — permanently.
  const runId = `${REORDER}-a`;
  await upsertAgentRun({ ...reorderBase, runId, status: "running" });
  await upsertAgentRun({ ...reorderBase, runId, status: "success" });
  await upsertAgentRun({ ...reorderBase, runId, status: "running" });

  const { rows } = await getPool().query(
    `SELECT status, finished_at FROM agent_runs WHERE run_id = $1`,
    [runId]
  );
  assert.equal(rows[0].status, "success", "a late start heartbeat overwrote the terminal status");
  assert.notEqual(rows[0].finished_at, null);
});

await test("a genuine retry BEFORE the run finishes still updates", async () => {
  // The guard keys on finished_at, not on the status alone — a second
  // 'running' for a run still in flight must not be ignored, or a fix for
  // reordering becomes a rule against heartbeats.
  const runId = `${REORDER}-b`;
  await upsertAgentRun({ ...reorderBase, runId, status: "running" });
  await upsertAgentRun({ ...reorderBase, runId, status: "running", errorSummary: "retrying" });
  const { rows } = await getPool().query(
    `SELECT status, error_summary, finished_at FROM agent_runs WHERE run_id = $1`,
    [runId]
  );
  assert.equal(rows[0].status, "running");
  assert.equal(rows[0].error_summary, "retrying");
  assert.equal(rows[0].finished_at, null);
});

await test("a contradictory row cannot hide a failed sibling", async () => {
  // Defence in depth for rows written before the guard existed: status
  // 'running' with finished_at set is a state the database can still hold, and
  // collapseRunGroup used to let it win every severity comparison.
  const wf = `${REORDER}-wf`;
  await getPool().query(
    `INSERT INTO agent_runs (run_id, tenant_id, workflow_id, status, started_at, finished_at)
     VALUES ($1, $2, $3, 'running', now() + interval '1 second', now()),
            ($4, $2, $3, 'failed',  now() + interval '1 second', now())`,
    [`${wf}-a`, REORDER, wf, `${wf}-b`]
  );
  const status = await getWidgetStatus(REORDER);
  assert.equal(status.status, "failed", "the contradictory row masked a real failure");
});

// ── What the In-App Widget is told ──────────────────────────────────────────
//
// getWidgetStatus had no test at all, and it is the only producer of the value
// a tenant's own users see, embedded in that tenant's own product.

const QUIET = `test-quiet-${Date.now()}`;
await upsertTenant({ tenantId: QUIET, name: QUIET });

await test("a tenant with nothing recorded is UNKNOWN, not success", async () => {
  // No agent_runs row, no history entry: the pipeline has never run, or the
  // worker has never reached this portal. That used to render as a green dot.
  const status = await getWidgetStatus(QUIET);
  assert.equal(status.status, "unknown");
  assert.equal(status.lastEventAt, null);
});

await test("a benign history entry is still success — that one IS a measurement", async () => {
  await getPool().query(
    `INSERT INTO agent_history_entries (tenant_id, entry_id, level, event, timestamp, hitl_resolved, raw)
     VALUES ($1, 'e-1', 'INFO', 'deploy ok', now(), FALSE, '{}'::jsonb)`,
    [QUIET]
  );
  const status = await getWidgetStatus(QUIET);
  assert.equal(status.status, "success");
});

await test("an unresolved CRITICAL entry outranks it", async () => {
  await getPool().query(
    `INSERT INTO agent_history_entries (tenant_id, entry_id, level, event, timestamp, hitl_resolved, raw)
     VALUES ($1, 'e-2', 'CRITICAL', 'gateway down', now() + interval '1 second', FALSE, '{}'::jsonb)`,
    [QUIET]
  );
  const status = await getWidgetStatus(QUIET);
  assert.equal(status.status, "failed");
  assert.equal(status.errorSummary, "gateway down");
});

await test("an open agent_runs row wins over the history fallback", async () => {
  await upsertAgentRun({ ...base, tenantId: QUIET, runId: `${QUIET}-open`, status: "running" });
  const status = await getWidgetStatus(QUIET);
  assert.equal(status.status, "running");
});

// Closed once, at the very end. It used to sit mid-file, so any test added
// after it died on "Cannot use a pool after calling end on the pool".
await getPool().end();

console.log(`\n${passed} passed`);
