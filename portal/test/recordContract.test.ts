// portal/test/recordContract.test.ts — the portal is held to the record contract
// it receives (contract/record/v1/, .agent-rfc/designs/record-contract.md).
//
// The validator here is hand-written TypeScript and cannot be generated from the
// published schema, so it is pinned to it: the schema number, the verdict and
// pillar catalogues and every limit are read from record.schema.json, not from
// the Python constants by regex; and every case a parser can decide is run.
//
// Run: node --experimental-strip-types --experimental-loader=./test/ts-extension-loader.mjs test/recordContract.test.ts

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { DEV_LIMITS, DEV_RECORD_SCHEMA, DEV_VERDICTS, PILLAR_KINDS, parseDevIngest } from "../lib/devIngest.ts";
import { recordBody, type RecordCase } from "./recordCases.ts";

const CONTRACT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "contract", "record", "v1");
const schema = JSON.parse(readFileSync(join(CONTRACT, "record.schema.json"), "utf8"));
const cases: RecordCase[] = JSON.parse(readFileSync(join(CONTRACT, "cases.json"), "utf8")).cases;
const protocol = readFileSync(join(CONTRACT, "protocol.md"), "utf8");
const defs = schema.$defs;

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

test("the record schema number is the published one", () => {
  assert.equal(DEV_RECORD_SCHEMA, schema.properties.schema.const);
});

test("the verdict and pillar catalogues are the published ones", () => {
  assert.deepEqual([...DEV_VERDICTS], defs.RecordCommit.properties.verdict.enum);
  const pillar = defs.RecordDesign.properties.pillars;
  assert.deepEqual([...PILLAR_KINDS], Object.values(pillar.patternProperties)[0].enum);
});

test("every limit is the published one", () => {
  assert.equal(DEV_LIMITS.commits, schema.properties.commits.maxItems);
  assert.equal(DEV_LIMITS.designs, schema.properties.designs.anyOf[0].maxItems);
  assert.equal(DEV_LIMITS.subject, defs.RecordCommit.properties.subject.maxLength);
  assert.equal(DEV_LIMITS.list, defs.RecordCommit.properties.errors.maxItems);
  assert.equal(DEV_LIMITS.text, defs.RecordCommit.properties.errors.items.maxLength);
  // The body size is a transport limit, stated in the protocol rather than the schema.
  assert.ok(protocol.includes(`**${DEV_LIMITS.bodyBytes.toLocaleString("en-US")} bytes**`));
});

test("the parser decides every case it can decide as the contract does", () => {
  // 401 and 413 are the handler's — token and size come before parsing
  // (recordContractDb.test.ts); the rest a parser alone must get right.
  const parseable = cases.filter((c) => c.token === "valid" && c.expect !== 413);
  assert.ok(parseable.length >= 5);
  for (const c of parseable) {
    const parsed = parseDevIngest(JSON.parse(recordBody(c)));
    assert.equal(parsed.ok, c.expect === 200, `${c.name}: expected ${c.expect}`);
  }
});

console.log(`${passed} passed`);
