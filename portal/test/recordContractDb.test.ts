// portal/test/recordContractDb.test.ts — the portal as a record-contract receiver,
// end to end against a real Postgres: every case in contract/record/v1/cases.json
// through the ingest handler with a real token, judged by status
// (.agent-rfc/designs/record-contract.md). The handler is what the route runs.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types --experimental-loader=./test/ts-extension-loader.mjs \
//        test/recordContractDb.test.ts

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { handleDevIngest } from "../lib/devIngestHandler.ts";
import { createIngestToken } from "../lib/ingestTokens.ts";
import { upsertTenant } from "../lib/tenants.ts";
import { recordBody, type RecordCase } from "./recordCases.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const CONTRACT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "contract", "record", "v1");
const cases: RecordCase[] = JSON.parse(readFileSync(join(CONTRACT, "cases.json"), "utf8")).cases;
const APP = `test-record-contract-${Date.now()}`;

await upsertTenant({ tenantId: APP, name: APP });
const token = await createIngestToken(APP, "record contract");

let failed = 0;
for (const c of cases) {
  const authorization =
    c.token === "valid" ? `Bearer ${token}` : c.token === "unknown" ? `Bearer asi_${"0".repeat(40)}` : null;
  const result = await handleDevIngest(authorization, recordBody(c));
  try {
    assert.equal(result.status, c.expect, `${c.name}: expected ${c.expect}, got ${result.status}`);
    console.log(`ok - ${c.name}`);
  } catch (err) {
    failed += 1;
    console.error(`not ok - ${c.name}`);
    console.error(err);
  }
}
if (failed) process.exitCode = 1;
console.log(`${cases.length - failed}/${cases.length} record contract cases`);
process.exit();
