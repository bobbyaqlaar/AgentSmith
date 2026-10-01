// portal/test/intakes.test.ts — what an author may put in a tenant intake, and
// the wire record the CLI receives (.agent-rfc/designs/portal-intake-pull.md).
// No database: the validator and the contract. test/intakesDb.test.ts drives
// the routes' handlers against Postgres.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { APP_ID } from "../lib/apps.ts";
import { ARCHITECTURE, INTAKE_IDES, INTAKE_LIMITS, INTAKE_STACKS, newIntakeToken, parseIntakeInput } from "../lib/intakes.ts";
import { hashToken } from "../lib/ingestTokens.ts";
import * as catalog from "../lib/intakeCatalog.ts";
import * as intakes from "../lib/intakes.ts";
import { ISOLATION_VALUES } from "../lib/isolation.ts";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CONTRACT = resolve(REPO_ROOT, "contract", "intake", "v1");
const SCHEMA = JSON.parse(readFileSync(resolve(CONTRACT, "record.schema.json"), "utf8"));
const FIXTURE = JSON.parse(readFileSync(resolve(CONTRACT, "fixture.json"), "utf8"));

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

const good = () => ({
  tenant_id: "acme-orders",
  stack: "python-fastapi",
  isolation: "shared",
  architecture: "hexagonal",
  agentic: false,
  ides: ["cursor"],
  rfc: {
    objective: "Take orders and confirm them.",
    acceptance_criteria: ["An order is stored"],
    files_to_modify: [],
  },
});

function refused(body: unknown, field: string) {
  const parsed = parseIntakeInput(body);
  assert.equal(parsed.ok, false, `accepted a bad ${field}`);
  if (!parsed.ok) assert.match(parsed.error, new RegExp(field.replace(".", "\\.")), "the refusal names the field");
}

// ── the validator ────────────────────────────────────────────────────────────

test("a complete intake is accepted as given", () => {
  const parsed = parseIntakeInput(good());
  assert.ok(parsed.ok);
  if (parsed.ok) assert.deepEqual(parsed.value, good());
});

test("only the fields that must be given are required", () => {
  const parsed = parseIntakeInput({
    tenant_id: "acme",
    stack: "go",
    rfc: { objective: "x", acceptance_criteria: ["y"] },
  });
  assert.ok(parsed.ok);
  if (parsed.ok) {
    assert.equal(parsed.value.isolation, "shared");
    assert.equal(parsed.value.architecture, null);
    assert.equal(parsed.value.agentic, false);
    assert.deepEqual(parsed.value.ides, []);
    assert.deepEqual(parsed.value.rfc.files_to_modify, []);
  }
});

test("tenant_id follows the portal's app id rule, the narrower of the two", () => {
  // Each of these passes runtime/cli.py TENANT_ID_PATTERN and would scaffold,
  // then be refused when the tenant registers as a portal app.
  for (const id of ["Acme", "acme_orders", "acme.orders", "acme-", "a".repeat(64)]) {
    refused({ ...good(), tenant_id: id }, "tenant_id");
  }
  for (const id of ["", "-acme", "acme orders", "ac\nme", "$(id)", "{{TENANT_ID}}"]) {
    refused({ ...good(), tenant_id: id }, "tenant_id");
  }
});

test("surrounding whitespace is trimmed, as an app id's is, and the clean id is what is kept", () => {
  const parsed = parseIntakeInput({ ...good(), tenant_id: "  acme\n" });
  assert.ok(parsed.ok);
  if (parsed.ok) assert.equal(parsed.value.tenant_id, "acme");
});

test("stack, isolation, architecture and agentic are closed or shaped", () => {
  refused({ ...good(), stack: "rust" }, "stack");
  refused({ ...good(), isolation: "private" }, "isolation");
  refused({ ...good(), architecture: "Hexagonal; rm -rf /" }, "architecture");
  refused({ ...good(), agentic: "yes" }, "agentic");
});

test("ides names only IDEs whose config can be written, each once", () => {
  refused({ ...good(), ides: ["gemini"] }, "ides");
  refused({ ...good(), ides: ["neutral"] }, "ides");
  refused({ ...good(), ides: ["cursor", "cursor"] }, "ides");
  refused({ ...good(), ides: "cursor" }, "ides");
});

test("the RFC needs an objective and at least one criterion, within limits", () => {
  refused({ ...good(), rfc: undefined }, "rfc");
  refused({ ...good(), rfc: { ...good().rfc, objective: "   " } }, "rfc.objective");
  refused({ ...good(), rfc: { ...good().rfc, objective: "x".repeat(INTAKE_LIMITS.objective + 1) } }, "rfc.objective");
  refused({ ...good(), rfc: { ...good().rfc, acceptance_criteria: [] } }, "rfc.acceptance_criteria");
  refused({ ...good(), rfc: { ...good().rfc, acceptance_criteria: Array(INTAKE_LIMITS.criteria + 1).fill("c") } }, "rfc.acceptance_criteria");
  refused({ ...good(), rfc: { ...good().rfc, files_to_modify: ["x".repeat(INTAKE_LIMITS.item + 1)] } }, "rfc.files_to_modify");
});

test("control characters are stripped, newlines and tabs kept", () => {
  const parsed = parseIntakeInput({ ...good(), rfc: { ...good().rfc, objective: "line one\u0007\nline\ttwo\u001b[31m" } });
  assert.ok(parsed.ok);
  if (parsed.ok) assert.equal(parsed.value.rfc.objective, "line one\nline\ttwo[31m");
});

test("text that is only control characters is empty, and refused", () => {
  refused({ ...good(), rfc: { ...good().rfc, objective: "\u0000\u0007" } }, "rfc.objective");
});

test("architecture is one of the catalogue's ids — a typo is caught where it was typed", () => {
  for (const a of catalog.INTAKE_ARCHITECTURES) assert.ok(parseIntakeInput({ ...good(), architecture: a.id }).ok, a.id);
  // "clean" is an alias the CLI resolves; the form sends ids, and the portal checks ids.
  for (const bad of ["hexagnal", "clean", "layered-ish"]) refused({ ...good(), architecture: bad }, "architecture");
});

test("a textarea becomes a list one way: trimmed, blank lines dropped", () => {
  assert.deepEqual(catalog.linesOf("  first \r\n\n second\n   \nthird"), ["first", "second", "third"]);
  assert.deepEqual(catalog.linesOf(""), []);
  assert.deepEqual(catalog.linesOf("\n \n"), []);
});

test("the catalogue moved, and lib/intakes.ts still answers for it", () => {
  // The form imports lib/intakeCatalog.ts; the server imports lib/intakes.ts.
  // They must be the same objects, not two copies that can drift.
  assert.equal(intakes.INTAKE_STACKS, catalog.INTAKE_STACKS);
  assert.equal(intakes.INTAKE_IDES, catalog.INTAKE_IDES);
  assert.equal(intakes.INTAKE_LIMITS, catalog.INTAKE_LIMITS);
  assert.equal(intakes.INTAKE_ARCHITECTURES, catalog.INTAKE_ARCHITECTURES);
});

test("the module the browser loads imports nothing the browser cannot", () => {
  const source = readFileSync(resolve(REPO_ROOT, "portal", "lib", "intakeCatalog.ts"), "utf8");
  assert.ok(!/^import /m.test(source), "lib/intakeCatalog.ts must stay import-free — the form loads it in the browser");
});

// ── the token ────────────────────────────────────────────────────────────────

test("an intake token is prefixed, random, and stored only as its hash", () => {
  const a = newIntakeToken();
  const b = newIntakeToken();
  assert.match(a.token, /^asx_[A-Za-z0-9_-]{43}$/);
  assert.notEqual(a.token, b.token);
  assert.equal(a.hash, hashToken(a.token));
  assert.ok(!a.hash.includes(a.token));
});

// ── the contract ─────────────────────────────────────────────────────────────

test("the contract's closed sets are the portal's", () => {
  // Three copies of one rule would be two opinions; the portal side is pinned
  // to Python by catalogs.test.ts, and the contract is pinned here.
  assert.deepEqual(SCHEMA.properties.stack.enum, [...INTAKE_STACKS]);
  assert.deepEqual(SCHEMA.properties.isolation.enum, [...ISOLATION_VALUES]);
  assert.deepEqual(SCHEMA.properties.ides.items.enum, [...INTAKE_IDES]);
  assert.equal(SCHEMA.properties.tenant_id.pattern, APP_ID.source);
  assert.equal(SCHEMA.properties.rfc.properties.objective.maxLength, INTAKE_LIMITS.objective);
  assert.equal(SCHEMA.properties.rfc.properties.acceptance_criteria.maxItems, INTAKE_LIMITS.criteria);
  assert.equal(SCHEMA.properties.rfc.properties.files_to_modify.maxItems, INTAKE_LIMITS.files);
  assert.equal(SCHEMA.properties.architecture.anyOf[1].pattern, ARCHITECTURE.source);
  for (const list of ["acceptance_criteria", "files_to_modify"]) {
    assert.equal(SCHEMA.properties.rfc.properties[list].items.maxLength, INTAKE_LIMITS.item, list);
  }
});

test("the fixture is a record the portal would have accepted", () => {
  const { schema_version, intake_id, expires_at, ...input } = FIXTURE;
  assert.equal(schema_version, 1);
  assert.match(intake_id, new RegExp(SCHEMA.properties.intake_id.pattern));
  assert.ok(!Number.isNaN(Date.parse(expires_at)));
  const parsed = parseIntakeInput(input);
  assert.ok(parsed.ok, parsed.ok ? "" : parsed.error);
  if (parsed.ok) assert.deepEqual(parsed.value, input);
});

test("the fixture carries exactly the contract's fields", () => {
  assert.deepEqual(Object.keys(FIXTURE).sort(), Object.keys(SCHEMA.properties).sort());
  assert.deepEqual([...SCHEMA.required].sort(), Object.keys(SCHEMA.properties).sort());
  assert.deepEqual(Object.keys(FIXTURE.rfc).sort(), Object.keys(SCHEMA.properties.rfc.properties).sort());
});

test("expiry is judged by one clock, the database's", () => {
  // The consume UPDATE compares expires_at with Postgres's now(). If anything in
  // lib/intakes.ts compared it with this process's clock, skew between the two
  // would let an intake read as live and then fail to consume, or the reverse.
  const source = readFileSync(resolve(REPO_ROOT, "portal", "lib", "intakes.ts"), "utf8");
  assert.ok(!/Date\.now\(\)|new Date\(\)\.getTime/.test(source), "lib/intakes.ts consults the process clock");
  assert.equal((source.match(/expires_at <= now\(\) AS expired/g) ?? []).length, 2, "both reads ask Postgres");
});

console.log(`\n${passed} passed`);
