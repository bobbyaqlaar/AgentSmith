// portal/test/opsContract.test.ts — the portal is held to the Ops contract it
// receives (contract/ops/v1/, .agent-rfc/designs/ops-contract.md).
//
// The validator is hand-written TypeScript and cannot be generated from the
// published schema, so it is pinned to it: the run statuses and the text limit
// are read from message.schema.json, and every case a parser can decide — a
// valid message or a refused one — is run through it. Storage and tokens are
// test/opsIngestDb.test.ts's.
//
// Run: node --experimental-strip-types --experimental-loader=./test/ts-extension-loader.mjs test/opsContract.test.ts

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { OPS_LIMITS, parseOpsMessage } from "../lib/opsIngest.ts";
import { AGENT_RUN_STATUSES } from "../lib/runStatus.ts";

const CONTRACT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "contract", "ops", "v1");
const schema = JSON.parse(readFileSync(join(CONTRACT, "message.schema.json"), "utf8"));
const fixture = JSON.parse(readFileSync(join(CONTRACT, "fixture.json"), "utf8"));
const cases = JSON.parse(readFileSync(join(CONTRACT, "cases.json"), "utf8")).cases;

let passed = 0;
function test(name: string, fn: () => void) {
  try {
    fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

/** A case's message: the fixture's of its kind, with `set` applied and `drop` removed. */
export function caseMessage(c: { message: string; set: Record<string, unknown>; drop: string[] }): Record<string, unknown> {
  const message: Record<string, unknown> = { ...fixture.messages[c.message], ...c.set };
  for (const key of c.drop) delete message[key];
  return message;
}

test("the run statuses are the published ones", () => {
  assert.deepEqual([...AGENT_RUN_STATUSES], schema.$defs.RunMessage.properties.status.enum);
});

test("the text limit is the published one", () => {
  const summary = schema.$defs.RunMessage.properties.error_summary.anyOf.find((b: { type: string }) => b.type === "string");
  assert.equal(OPS_LIMITS.text, summary.maxLength);
});

test("every fixture message is valid", () => {
  for (const [kind, message] of Object.entries(fixture.messages)) {
    const parsed = parseOpsMessage(message);
    assert.ok(parsed.ok, `${kind}: ${parsed.ok ? "" : parsed.error}`);
  }
});

for (const c of cases) {
  test(`case: ${c.name}`, () => {
    const parsed = parseOpsMessage(caseMessage(c));
    if (c.expect === 200) assert.ok(parsed.ok, parsed.ok ? "" : parsed.error);
    else if (c.expect === 400) assert.ok(!parsed.ok, "accepted a message the contract refuses");
  });
}

test("a settings message stores no secret even when the parser is asked about one", () => {
  const parsed = parseOpsMessage({ ...fixture.messages.settings, replay_webhook_secret: "x" });
  assert.ok(!parsed.ok);
});

console.log(`\n${passed} passed`);
