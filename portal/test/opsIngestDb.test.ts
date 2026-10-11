// portal/test/opsIngestDb.test.ts — the Ops ingest end to end, against a real
// Postgres (contract/ops/v1): token → validation → storage.
//
// Runs in the test:db lane. The properties under test: the token alone decides
// the app, and a CI (dev) token is not an Ops token, nor the reverse; each kind
// is stored; an id another app holds is never written over; settings carry no
// secret; the replay key is the portal's to issue; the deprecated history route
// stores no secret any more.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/opsIngestDb.test.ts

import assert from "node:assert/strict";

import { issueReplayKey } from "../lib/apps.ts";
import { getPool } from "../lib/db.ts";
import { handleDevIngest } from "../lib/devIngestHandler.ts";
import { createIngestToken } from "../lib/ingestTokens.ts";
import { handleOpsIngest } from "../lib/opsIngest.ts";
import { replayStatus, upsertTenant } from "../lib/tenants.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const RUN = Date.now();
const APP_A = `test-ops-a-${RUN}`;
const APP_B = `test-ops-b-${RUN}`;
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

const bearer = (token: string) => `Bearer ${token}`;
const run = (runId: string, extra: Record<string, unknown> = {}) =>
  JSON.stringify({ schema: 1, kind: "run", run_id: runId, status: "success", ...extra });
const dead = (taskId: string) =>
  JSON.stringify({ schema: 1, kind: "dead_letter", task_id: taskId, error: "boom", payload: { a: 1 }, reason: "infra_error" });

await upsertTenant({ tenantId: APP_A, name: APP_A });
await upsertTenant({ tenantId: APP_B, name: APP_B });
const opsA = await createIngestToken(APP_A, "test", "ops");
const opsB = await createIngestToken(APP_B, "test", "ops");
const devA = await createIngestToken(APP_A, "test", "dev");

await test("a run is stored under the token's app, whatever the body names", async () => {
  const result = await handleOpsIngest(bearer(opsA), run(`run-a-${RUN}`, { tenant_id: APP_B, tenantId: APP_B }));
  assert.equal(result.status, 200, JSON.stringify(result.body));
  const { rows } = await getPool().query(`SELECT tenant_id FROM agent_runs WHERE run_id = $1`, [`run-a-${RUN}`]);
  assert.equal(rows[0].tenant_id, APP_A);
});

await test("a CI (dev) token is not an Ops token", async () => {
  const result = await handleOpsIngest(bearer(devA), run(`run-dev-${RUN}`));
  assert.equal(result.status, 401);
});

await test("an Ops token is not a CI (dev) token", async () => {
  const result = await handleDevIngest(bearer(opsA), "{}");
  assert.equal(result.status, 401);
});

await test("a run id another app holds is never written over", async () => {
  const result = await handleOpsIngest(bearer(opsB), run(`run-a-${RUN}`, { status: "failed" }));
  assert.equal(result.status, 409);
  const { rows } = await getPool().query(`SELECT tenant_id, status FROM agent_runs WHERE run_id = $1`, [`run-a-${RUN}`]);
  assert.deepEqual(rows[0], { tenant_id: APP_A, status: "success" });
});

await test("a late running report does not un-finish a run", async () => {
  await handleOpsIngest(bearer(opsA), run(`run-a-${RUN}`, { status: "running" }));
  const { rows } = await getPool().query(`SELECT status FROM agent_runs WHERE run_id = $1`, [`run-a-${RUN}`]);
  assert.equal(rows[0].status, "success");
});

await test("a dead letter is stored once, and resending it is safe", async () => {
  const first = await handleOpsIngest(bearer(opsA), dead(`task-a-${RUN}`));
  const again = await handleOpsIngest(bearer(opsA), dead(`task-a-${RUN}`));
  assert.deepEqual([first.status, first.body, again.status, again.body], [200, { stored: 1 }, 200, { stored: 0 }]);
  const { rows } = await getPool().query(`SELECT tenant_id, status FROM dlq_entries WHERE task_id = $1`, [`task-a-${RUN}`]);
  assert.deepEqual(rows, [{ tenant_id: APP_A, status: "pending" }]);
});

await test("a task id another app holds is refused", async () => {
  const result = await handleOpsIngest(bearer(opsB), dead(`task-a-${RUN}`));
  assert.equal(result.status, 409);
});

await test("settings store the cap and the webhook, and keep what a message leaves out", async () => {
  const first = await handleOpsIngest(bearer(opsA), JSON.stringify({
    schema: 1, kind: "settings", budget_cap_usd: 12.5, replay_webhook_url: "https://worker.a.example/replay",
  }));
  assert.equal(first.status, 200);
  await handleOpsIngest(bearer(opsA), JSON.stringify({ schema: 1, kind: "settings", budget_cap_usd: 20 }));
  const { rows } = await getPool().query(`SELECT budget_cap_usd, replay_webhook_url FROM tenants WHERE tenant_id = $1`, [APP_A]);
  assert.deepEqual(rows[0], { budget_cap_usd: 20, replay_webhook_url: "https://worker.a.example/replay" });
});

await test("a changed replay URL is audited, an unchanged one is not", async () => {
  const audits = async () => (await getPool().query(
    `SELECT details FROM audit_log WHERE tenant_id = $1 AND details->>'action' = 'replay_webhook_url_changed'`, [APP_A])).rows;
  const before = (await audits()).length;
  await handleOpsIngest(bearer(opsA), JSON.stringify({ schema: 1, kind: "settings", replay_webhook_url: "https://worker.a.example/replay" }));
  assert.equal((await audits()).length, before, "the same URL again is no change");
  await handleOpsIngest(bearer(opsA), JSON.stringify({ schema: 1, kind: "settings", replay_webhook_url: "https://worker.a2.example/replay" }));
  const rows = await audits();
  assert.equal(rows.length, before + 1);
  assert.ok(rows.some((r: { details: Record<string, unknown> }) =>
    r.details.from === "https://worker.a.example/replay" && r.details.to === "https://worker.a2.example/replay"));
});

await test("settings carrying a secret are refused and store nothing", async () => {
  const result = await handleOpsIngest(bearer(opsA), JSON.stringify({ schema: 1, kind: "settings", replay_webhook_secret: "x" }));
  assert.equal(result.status, 400);
  assert.equal((await replayStatus(APP_A)).keyIssued, false);
});

await test("the replay key is the portal's to issue, and is audited without its value", async () => {
  const key = await issueReplayKey(APP_A, "alice");
  assert.match(key, /^[0-9a-f]{64}$/);
  assert.equal((await replayStatus(APP_A)).keyIssued, true);
  const { rows } = await getPool().query(
    `SELECT details FROM audit_log WHERE tenant_id = $1 AND details->>'action' = 'replay_key_issued'`, [APP_A]);
  assert.equal(rows.length, 1);
  assert.ok(!JSON.stringify(rows[0].details).includes(key));
});

await test("the deprecated history route sets neither a replay URL nor a secret", async () => {
  // Under the one token every tenant shared, it would let any holder point
  // another tenant's signed replays at an address of its choosing.
  process.env.OPS_PORTAL_SYNC_TOKEN = "legacy-shared-token-for-this-test";
  const { POST } = await import("../app/api/sync/history/route.ts");
  const before = await replayStatus(APP_B);
  const response = await POST(new Request("http://portal.test/api/sync/history", {
    method: "POST",
    headers: { authorization: "Bearer legacy-shared-token-for-this-test", "content-type": "application/json" },
    body: JSON.stringify({ tenantId: APP_B, entries: [], replayWebhookUrl: "https://attacker.example/replay",
                           replayWebhookSecret: "chosen-by-the-caller" }),
  }));
  assert.ok(response.status < 400, `status ${response.status}`);
  assert.deepEqual(await replayStatus(APP_B), before);
});

await test("no token, an unknown token and an oversize body are refused", async () => {
  assert.equal((await handleOpsIngest(null, run("x"))).status, 401);
  assert.equal((await handleOpsIngest(bearer("aso_unknown"), run("x"))).status, 401);
  assert.equal((await handleOpsIngest(bearer(opsA), "x".repeat(1_000_001))).status, 413);
});

// The apps stay, as in the other database tests: their audit rows are
// append-only and reference them. Every id here is unique to this run.
await getPool().query(`DELETE FROM dlq_entries WHERE tenant_id IN ($1, $2)`, [APP_A, APP_B]);
console.log(`\n${passed} passed`);
await getPool().end();
