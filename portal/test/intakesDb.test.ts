// portal/test/intakesDb.test.ts — a tenant intake against a real Postgres
// (.agent-rfc/designs/portal-intake-pull.md): issued with an audit row, read by
// its own token only, used once, and refused with a reason that says what to do.
//
// Drives lib/intakes.ts's handlers — the functions the routes adapt — with
// nothing mocked.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/intakesDb.test.ts

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { getPool } from "../lib/db.ts";
import { hashToken } from "../lib/ingestTokens.ts";
import {
  createIntake,
  handleScaffoldConsume,
  handleScaffoldRead,
  parseIntakeInput,
  type IntakeInput,
} from "../lib/intakes.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const SCHEMA = JSON.parse(
  readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "contract", "intake", "v1", "record.schema.json"), "utf8"),
);

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

const RUN = Date.now();
function input(suffix: string): IntakeInput {
  const parsed = parseIntakeInput({
    tenant_id: `test-intake-${RUN}-${suffix}`,
    stack: "python-fastapi",
    architecture: "hexagonal",
    ides: ["cursor"],
    rfc: { objective: "Take orders.", acceptance_criteria: ["An order is stored"] },
  });
  assert.ok(parsed.ok);
  return (parsed as { ok: true; value: IntakeInput }).value;
}
const bearer = (token: string) => `Bearer ${token}`;

async function auditFor(intakeId: string) {
  const { rows } = await getPool().query(
    `SELECT event_type, actor_id, tenant_id, details FROM audit_log
      WHERE details->>'intake_id' = $1 ORDER BY "timestamp"`,
    [intakeId],
  );
  return rows as { event_type: string; actor_id: string; tenant_id: string | null; details: Record<string, unknown> }[];
}

await test("issuing an intake stores only the token's hash, and audits who issued it", async () => {
  const issued = await createIntake(input("issue"), "alice");
  assert.match(issued.token, /^asx_/);
  const { rows } = await getPool().query(`SELECT token_hash, created_by FROM tenant_intakes WHERE intake_id = $1`, [issued.intake_id]);
  assert.equal(rows[0].token_hash, hashToken(issued.token));
  assert.equal(rows[0].created_by, "alice");

  const [event] = await auditFor(issued.intake_id);
  assert.equal(event.event_type, "config_change");
  assert.equal(event.actor_id, "alice");
  assert.equal(event.details.action, "intake_issued");
  // Not registered yet, so not a foreign key the audit row can carry.
  assert.equal(event.tenant_id, null);
  assert.ok(!JSON.stringify(event.details).includes(issued.token), "the token reached the audit log");
});

await test("the token reads its intake as the contract's record, and can read it again", async () => {
  const issued = await createIntake(input("read"), "alice");
  const first = await handleScaffoldRead(bearer(issued.token), issued.intake_id);
  assert.equal(first.status, 200);
  assert.deepEqual(Object.keys(first.body).sort(), Object.keys(SCHEMA.properties).sort());
  assert.equal(first.body.intake_id, issued.intake_id);
  assert.deepEqual(first.body.ides, ["cursor"]);
  assert.equal((await handleScaffoldRead(bearer(issued.token), issued.intake_id)).status, 200, "a read used it up");
});

await test("no token, or an unknown one, is a 401", async () => {
  const issued = await createIntake(input("unknown"), "alice");
  assert.equal((await handleScaffoldRead(null, issued.intake_id)).status, 401);
  assert.equal((await handleScaffoldRead("Basic abc", issued.intake_id)).status, 401);
  assert.equal((await handleScaffoldRead(bearer("asx_not-a-real-token"), issued.intake_id)).status, 401);
});

await test("the token decides: another intake's id is a 404, as an id that does not exist is", async () => {
  const mine = await createIntake(input("mine"), "alice");
  const theirs = await createIntake(input("theirs"), "bob");
  const wrongId = await handleScaffoldRead(bearer(mine.token), theirs.intake_id);
  const noId = await handleScaffoldRead(bearer(mine.token), "999999999999");
  assert.equal(wrongId.status, 404);
  assert.equal(noId.status, 404);
  assert.ok(!JSON.stringify(wrongId.body).includes("test-intake"), "a 404 leaked the other intake's contents");
  assert.equal((await handleScaffoldConsume(bearer(mine.token), theirs.intake_id)).status, 404);
  assert.equal((await handleScaffoldRead(bearer(theirs.token), theirs.intake_id)).status, 200, "theirs was touched");
});

await test("consuming uses the intake once, audits it against its author, and then refuses it", async () => {
  const issued = await createIntake(input("consume"), "alice");
  const used = await handleScaffoldConsume(bearer(issued.token), issued.intake_id);
  assert.equal(used.status, 200);

  const events = await auditFor(issued.intake_id);
  const consumed = events.find((e) => e.details.action === "intake_consumed");
  assert.ok(consumed, "the consume was not audited");
  assert.equal(consumed.event_type, "tenant_created");
  assert.equal(consumed.actor_id, "alice");
  assert.equal(consumed.details.authenticated_by, "intake_token");

  for (const again of [
    await handleScaffoldConsume(bearer(issued.token), issued.intake_id),
    await handleScaffoldRead(bearer(issued.token), issued.intake_id),
  ]) {
    assert.equal(again.status, 410);
    assert.equal(again.body.reason, "consumed");
  }
});

await test("an expired intake is refused with a different reason from a used one", async () => {
  const issued = await createIntake(input("expired"), "alice");
  await getPool().query(`UPDATE tenant_intakes SET expires_at = now() - interval '1 second' WHERE intake_id = $1`, [issued.intake_id]);
  const read = await handleScaffoldRead(bearer(issued.token), issued.intake_id);
  const consume = await handleScaffoldConsume(bearer(issued.token), issued.intake_id);
  for (const r of [read, consume]) {
    assert.equal(r.status, 410);
    assert.equal(r.body.reason, "expired");
    assert.match(String(r.body.error), /new intake/);
  }
  const { rows } = await getPool().query(`SELECT consumed_at FROM tenant_intakes WHERE intake_id = $1`, [issued.intake_id]);
  assert.equal(rows[0].consumed_at, null, "an expired intake was marked used");
});

await test("two consumes racing each other: exactly one succeeds, and one audit row is written", async () => {
  const issued = await createIntake(input("race"), "alice");
  const results = await Promise.all(
    Array.from({ length: 5 }, () => handleScaffoldConsume(bearer(issued.token), issued.intake_id)),
  );
  assert.equal(results.filter((r) => r.status === 200).length, 1, JSON.stringify(results.map((r) => r.status)));
  assert.ok(results.filter((r) => r.status !== 200).every((r) => r.status === 410 && r.body.reason === "consumed"));
  const consumed = (await auditFor(issued.intake_id)).filter((e) => e.details.action === "intake_consumed");
  assert.equal(consumed.length, 1);
});

await test("an intake expires 24 hours after it is issued", async () => {
  const issued = await createIntake(input("ttl"), "alice");
  const hours = (Date.parse(issued.expires_at) - Date.now()) / 3_600_000;
  assert.ok(hours > 23.9 && hours <= 24, `expires in ${hours} hours`);
});

await getPool().query(`DELETE FROM tenant_intakes WHERE tenant_id LIKE $1`, [`test-intake-${RUN}-%`]);
await getPool().end();
console.log(`\n${passed} passed`);
