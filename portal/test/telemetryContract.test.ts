// portal/test/telemetryContract.test.ts — the portal against the telemetry
// contract (contract/telemetry/v1, .agent-rfc/designs/telemetry-contract.md).
//
// The portal is both sides of the wire: it EMITS spans (its Resource) and it
// READS them back from Phoenix (promotions.ts). Each side is held to the one
// published catalogue rather than to a copy of it — the catalogue cannot be
// imported from TypeScript, so it is read as the file another platform reads.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { TELEMETRY_CONTRACT, resourceAttributes } from "../lib/spanIdentity.ts";

const here = dirname(fileURLToPath(import.meta.url));
const contract = join(here, "..", "..", "contract", "telemetry", "v1");

interface Entry {
  name: string;
  where: string;
  family?: boolean;
  type?: string;
  requirement?: string;
}

const catalogue = JSON.parse(readFileSync(join(contract, "attributes.json"), "utf-8")) as {
  contract: number;
  entries: Entry[];
};

function lookup(where: string, name: string): Entry | undefined {
  const exact = catalogue.entries.find((e) => e.where === where && e.name === name && !e.family);
  if (exact) return exact;
  return catalogue.entries
    .filter((e) => e.where === where && e.family && name.startsWith(e.name))
    .sort((a, b) => b.name.length - a.name.length)[0];
}

function typeOf(value: unknown): string {
  if (typeof value === "string") return "string";
  if (typeof value === "boolean") return "bool";
  return Number.isInteger(value) ? "int" : "double";
}

await test("the portal speaks the catalogue's contract", () => {
  assert.equal(TELEMETRY_CONTRACT, catalogue.contract);
  assert.equal(resourceAttributes({} as NodeJS.ProcessEnv)["governance.telemetry.contract"], catalogue.contract);
});

await test("every attribute on the portal's Resource is catalogued, with its type", () => {
  const attrs = resourceAttributes({ ENVIRONMENT: "staging", AGENT_OWNER_ID: "o@example.test" } as NodeJS.ProcessEnv);
  for (const [name, value] of Object.entries(attrs)) {
    const entry = lookup("resource", name);
    assert.ok(entry, `${name} is not in contract/telemetry/v1/attributes.json`);
    if (entry.type === "number") assert.ok(typeof value === "number", name);
    else if (entry.type) assert.equal(typeOf(value), entry.type, name);
  }
  for (const entry of catalogue.entries.filter((e) => e.where === "resource" && e.requirement === "required")) {
    assert.ok(entry.name in attrs, `the portal's Resource lacks the required ${entry.name}`);
  }
});

await test("every span attribute the portal reads back is catalogued", () => {
  const source = readFileSync(join(here, "..", "lib", "promotions.ts"), "utf-8");
  const read = [...source.matchAll(/attrs\["([^"]+)"\]/g)].map((m) => m[1]);
  assert.ok(read.length > 0, "promotions.ts reads no span attribute — the pattern no longer matches it");
  for (const name of read) {
    assert.ok(lookup("span", name), `promotions.ts reads ${name}, which the catalogue does not define`);
  }
});
