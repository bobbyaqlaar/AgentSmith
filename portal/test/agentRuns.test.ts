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
import { upsertAgentRun } from "../lib/runStatus.ts";
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

await getPool().query(`DELETE FROM agent_runs WHERE tenant_id = $1`, [TENANT]);
await getPool().query(`DELETE FROM tenants WHERE tenant_id = $1`, [TENANT]);
await getPool().end();

console.log(`\n${passed} passed`);
