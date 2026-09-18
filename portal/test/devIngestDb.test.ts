// portal/test/devIngestDb.test.ts — the Dev ingest end to end, against a real
// Postgres (portal phase 1, S3): token → validation → storage.
//
// Runs in the test:db lane, like agentRuns.test.ts. The properties under test:
// a token writes only its own app's commits, a refused body stores nothing,
// and the same run posted twice leaves one row per commit.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/devIngestDb.test.ts

import assert from "node:assert/strict";

import { getPool } from "../lib/db.ts";
import { DEV_RECORD_SCHEMA } from "../lib/devIngest.ts";
import { handleDevIngest } from "../lib/devIngestHandler.ts";
import { createIngestToken, revokeIngestTokens } from "../lib/ingestTokens.ts";
import { upsertTenant } from "../lib/tenants.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const RUN = Date.now();
const APP_A = `test-dev-a-${RUN}`;
const APP_B = `test-dev-b-${RUN}`;
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

const sha = (n: number) => n.toString(16).padStart(40, "0");

function record(commits: number[], overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    schema: DEV_RECORD_SCHEMA,
    generated_at: "2026-09-18T10:00:00Z",
    base: null,
    head: sha(commits[commits.length - 1]),
    range_caveat: null,
    ci_run_url: "https://github.com/o/r/actions/runs/7",
    commits: commits.map((n) => ({
      commit: sha(n), parent: null, subject: `feat: ${n}`, author_name: "Ada", author_email: "ada@example.com",
      committed_at: "2026-09-18T10:00:00Z", adopted: true, gated: true, verdict: "passed",
      errors: [], notes: [], repairs: [], design: null, review: null,
    })),
    ...overrides,
  });
}

async function count(table: string, app: string): Promise<number> {
  const { rows } = await getPool().query(`SELECT count(*)::int AS n FROM ${table} WHERE tenant_id = $1`, [app]);
  return rows[0].n;
}

await upsertTenant({ tenantId: APP_A, name: APP_A });
await upsertTenant({ tenantId: APP_B, name: APP_B });
const tokenA = await createIngestToken(APP_A, "test");

await test("a valid record is stored for the token's app", async () => {
  const result = await handleDevIngest(`Bearer ${tokenA}`, record([1, 2]));
  assert.equal(result.status, 200, JSON.stringify(result.body));
  assert.equal(await count("dev_commits", APP_A), 2);
  assert.equal(await count("dev_ingest_runs", APP_A), 1);
});

await test("the same run posted twice leaves one row per commit", async () => {
  const again = await handleDevIngest(`Bearer ${tokenA}`, record([1, 2]));
  assert.equal(again.status, 200);
  assert.equal(await count("dev_commits", APP_A), 2);
});

await test("SECURITY: a token writes its own app, whatever the body says", async () => {
  const result = await handleDevIngest(`Bearer ${tokenA}`, record([3], { app: APP_B, tenant_id: APP_B }));
  assert.equal(result.status, 200);
  assert.equal(await count("dev_commits", APP_B), 0);
});

await test("a refused body stores nothing — not the valid half", async () => {
  const before = await count("dev_commits", APP_A);
  const bad = JSON.parse(record([10, 11]));
  bad.commits[1].verdict = "approved";
  const result = await handleDevIngest(`Bearer ${tokenA}`, JSON.stringify(bad));
  assert.equal(result.status, 400);
  assert.match(String(result.body.error), /verdict/);
  assert.equal(await count("dev_commits", APP_A), before);
});

await test("no token, an unknown token and a revoked token are each refused", async () => {
  // Two different 401s: "none was sent" sends an operator to the CI secret,
  // "not one we know" to the portal's Apps page. One message for both would
  // send half of them to the wrong place.
  const missing = await handleDevIngest(null, record([20]));
  assert.equal(missing.status, 401);
  assert.match(String(missing.body.error), /Bearer .* is required/);
  const unknown = await handleDevIngest("Bearer not-a-token", record([20]));
  assert.equal(unknown.status, 401);
  assert.match(String(unknown.body.error), /unknown or revoked/);
  const tokenB = await createIngestToken(APP_B, "test");
  assert.equal((await handleDevIngest(`Bearer ${tokenB}`, record([20]))).status, 200);
  await revokeIngestTokens(APP_B);
  assert.equal((await handleDevIngest(`Bearer ${tokenB}`, record([21]))).status, 401);
});

await test("a body over the size limit is refused before it is parsed", async () => {
  const result = await handleDevIngest(`Bearer ${tokenA}`, " ".repeat(2_000_001));
  assert.equal(result.status, 413);
});

await test("malformed JSON is the caller's 400, not a 500", async () => {
  const result = await handleDevIngest(`Bearer ${tokenA}`, "{not json");
  assert.equal(result.status, 400);
});

await getPool().query(`DELETE FROM tenants WHERE tenant_id = ANY($1)`, [[APP_A, APP_B]]);
await getPool().end();
console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
