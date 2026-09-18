// portal/test/appsDb.test.ts — Administration › Apps against a real Postgres
// (portal phase 1, S6). Every change is audited in the same transaction, with
// the person who made it.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/appsDb.test.ts

import assert from "node:assert/strict";

import { AppExistsError, createApp, revokeAppIngestTokens, rotateIngestToken, updateApp } from "../lib/apps.ts";
import { getPool } from "../lib/db.ts";
import { ingestTokenStatus, resolveIngestToken } from "../lib/ingestTokens.ts";
import { getTenant } from "../lib/tenants.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const APP = `test-apps-${Date.now()}`;
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

async function audit(): Promise<{ event_type: string; actor_id: string; details: Record<string, unknown> }[]> {
  const { rows } = await getPool().query(
    `SELECT event_type, actor_id, details FROM audit_log WHERE tenant_id = $1 ORDER BY "timestamp"`,
    [APP],
  );
  return rows;
}

const input = { name: "Test app", repoUrl: "https://github.com/acme/app", repoProvider: "github" as const, defaultBranch: "main" };

await test("registering an app stores its repository and audits who did it", async () => {
  await createApp({ id: APP, ...input }, "alice");
  const app = await getTenant(APP);
  assert.equal(app?.repoUrl, "https://github.com/acme/app");
  assert.equal(app?.repoProvider, "github");
  const [event] = await audit();
  assert.equal(event.event_type, "tenant_created");
  assert.equal(event.actor_id, "alice");
});

await test("registering an id that exists is refused, not an overwrite", async () => {
  await assert.rejects(() => createApp({ id: APP, ...input, name: "Hijack" }, "mallory"), AppExistsError);
  assert.equal((await getTenant(APP))?.name, "Test app");
});

await test("an edit changes the app and audits what changed", async () => {
  await updateApp(APP, { ...input, defaultBranch: "trunk" }, "bob");
  assert.equal((await getTenant(APP))?.defaultBranch, "trunk");
  const last = (await audit()).at(-1)!;
  assert.equal(last.event_type, "config_change");
  assert.equal(last.actor_id, "bob");
  assert.deepEqual(last.details.changed, ["defaultBranch"]);
});

await test("rotating the ingest token revokes the old one and audits it", async () => {
  const first = await rotateIngestToken(APP, "alice");
  assert.equal(await resolveIngestToken(first), APP);
  const second = await rotateIngestToken(APP, "alice");
  assert.equal(await resolveIngestToken(first), null, "the old token stops working at once");
  assert.equal(await resolveIngestToken(second), APP);
  const [status] = await ingestTokenStatus([APP]);
  assert.equal(status.active, 1);
  const last = (await audit()).at(-1)!;
  assert.equal(last.details.action, "ingest_token_issued");
  assert.equal(last.details.revoked, 1);
  assert.ok(!JSON.stringify(last.details).includes(second), "SECURITY: the token never reaches the audit log");
});

await test("revoking leaves no working token, and says how many it revoked", async () => {
  const revoked = await revokeAppIngestTokens(APP, "carol");
  assert.equal(revoked, 1);
  const [status] = await ingestTokenStatus([APP]);
  assert.equal(status.active, 0);
  assert.equal((await audit()).at(-1)!.details.action, "ingest_token_revoked");
});

// The app is left in place: audit_log is append-only and references it, so a
// tenant with audit history cannot be deleted — by design.
await getPool().end();
console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
