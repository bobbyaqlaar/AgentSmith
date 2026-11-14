// portal/test/incidentsDb.test.ts — incidents against a real Postgres (the 4.1.0 review's
// second pass, P2-R21): a close is audited only when it closed an open incident of this app.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/incidentsDb.test.ts

import assert from "node:assert/strict";

import { createApp } from "../lib/apps.ts";
import { getPool } from "../lib/db.ts";
import { closeIncident, openIncident } from "../lib/incidents.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const APP = `test-incidents-${Date.now()}`;
const OTHER = `${APP}-other`;
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

async function closes(tenantId: string): Promise<number> {
  const { rows } = await getPool().query(
    `SELECT count(*)::int AS n FROM audit_log WHERE tenant_id = $1 AND event_type = 'incident' AND details->>'action' = 'close'`,
    [tenantId],
  );
  return rows[0].n;
}

const input = { name: "Test app", repoUrl: "https://github.com/acme/app", repoProvider: "github" as const, defaultBranch: "main" };
await createApp({ id: APP, ...input }, "alice");
await createApp({ id: OTHER, ...input }, "alice");

await test("an open incident is closed once, and audited once", async () => {
  const id = await openIncident({ tenantId: APP, title: "Wrong answers", severity: "high", details: "", actor: "ops@x" });
  assert.equal(await closeIncident(APP, id, "ops@x"), true);
  assert.equal(await closes(APP), 1);
  assert.equal(await closeIncident(APP, id, "ops@x"), false); // a second click changes nothing
  assert.equal(await closes(APP), 1);
});

await test("another app's incident is not closed through this one, and nothing is audited", async () => {
  const id = await openIncident({ tenantId: OTHER, title: "Theirs", severity: "low", details: "", actor: "ops@x" });
  assert.equal(await closeIncident(APP, id, "ops@x"), false);
  assert.equal(await closes(APP), 1);
  const { rows } = await getPool().query(`SELECT status FROM incidents WHERE incident_id = $1`, [id]);
  assert.equal(rows[0].status, "open");
});

console.log(`${passed} passed`);
await getPool().end();
process.exit(process.exitCode || 0);
