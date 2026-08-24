// portal/test/catalogs.test.ts — the catalogs that also exist in SQL.
//
// Three closed sets are declared twice: once in TypeScript, where the type is
// derived from an array and one guard checks it, and once as a `CHECK (... IN
// (...))` in db/schema.sql. The TS half is already disciplined — lib/authz's
// ROLES, lib/isolation's ISOLATION_VALUES, lib/runStatus's AGENT_RUN_STATUSES
// each have exactly one definition — but nothing connected any of them to the
// constraint the database enforces.
//
// That gap is silent in the worst way: adding a value in TypeScript makes the
// route accept it, and Postgres rejects it at the moment a real request writes
// it. A 500 in production for a change that type-checked, passed review, and
// passed every test.
//
// The database cannot import TypeScript, so this is the same treatment
// lib/environment.ts's mirror of runtime/environment.py gets: read the other
// side and compare.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { ROLES } from "../lib/authz.ts";
import { ISOLATION_VALUES } from "../lib/isolation.ts";
import { AGENT_RUN_STATUSES } from "../lib/runStatus.ts";
import { AUDIT_EVENT_TYPES } from "../lib/auditSignature.ts";

const PORTAL = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SCHEMA = readFileSync(join(PORTAL, "db", "schema.sql"), "utf8");

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

/**
 * The value list of `CHECK (<column> IN ('a', 'b'))` for one column.
 *
 * Throws rather than returning empty when the constraint is not found: a
 * missing constraint must fail this test, not turn every comparison below into
 * `[] === []`.
 */
function checkConstraintValues(column: string): string[] {
  const pattern = new RegExp(`CHECK\\s*\\(\\s*${column}\\s+IN\\s*\\(([^)]*)\\)`, "i");
  const match = SCHEMA.match(pattern);
  assert.ok(match, `no CHECK (${column} IN (...)) constraint found in db/schema.sql`);
  return [...match[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
}

test("tenants.isolation matches ISOLATION_VALUES", () => {
  assert.deepEqual(checkConstraintValues("isolation").sort(), [...ISOLATION_VALUES].sort());
});

test("agent_runs.status matches AGENT_RUN_STATUSES", () => {
  // `unknown` must NOT be here: it is portal-side only, meaning "nothing has
  // been recorded", and nothing ever writes it to a row.
  const sql = checkConstraintValues("status");
  assert.deepEqual(sql.sort(), [...AGENT_RUN_STATUSES].sort());
  assert.ok(!sql.includes("unknown"), "unknown is not a storable run status");
});

test("audit_log.event_type matches AUDIT_EVENT_TYPES", () => {
  assert.deepEqual(checkConstraintValues("event_type").sort(), [...AUDIT_EVENT_TYPES].sort());
});

test("ROLES has no SQL counterpart to drift from", () => {
  // Stated rather than assumed: roles live in OPS_PORTAL_USERS / OPS_PORTAL_SSO_USERS
  // (environment, not schema), so if a `role` column ever appears here, this
  // test is where the fourth copy should be caught.
  assert.ok(!/CHECK\s*\(\s*role\s+IN/i.test(SCHEMA), "a role CHECK now exists — pin it above");
  assert.deepEqual([...ROLES], ["viewer", "operator", "admin"]);
});

test("the constraint reader actually reads constraints", () => {
  // Guard on the guard: if the regex stopped matching, every deepEqual above
  // would compare two empty arrays and pass having checked nothing.
  assert.ok(checkConstraintValues("isolation").length >= 2);
  assert.throws(() => checkConstraintValues("no_such_column"));
});

console.log(`\n${passed} passed`);
