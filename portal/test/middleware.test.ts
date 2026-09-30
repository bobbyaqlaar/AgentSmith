// portal/test/middleware.test.ts — which paths skip human authentication.
//
// middleware.ts excludes a handful of machine-to-machine paths from basic auth
// and SSO; each authenticates inside its own handler instead. Until
// 2026-10-01 nothing tested that list, though it is the portal's widest door:
// plain prefix matching here was once an auth bypass (docs/PRODUCT_ARCHIVE.md
// 2.6), and every exclusion is anchored `(?:/|$)` for that reason. Added with
// /api/dev/scaffold (.agent-rfc/designs/portal-intake-pull.md), and it pins the
// exclusions that were already there.
//
// Reads the matcher from the source rather than importing middleware.ts, which
// pulls in Next: the matcher is a literal, and a literal is what is tested.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "..", "middleware.ts"), "utf8");
const literal = SOURCE.match(/matcher:\s*("(?:[^"\\]|\\.)*")/);
assert.ok(literal, "could not find config.matcher in middleware.ts — this test would check nothing");
const PATTERN: string = JSON.parse(literal[1]);
const MATCHER = new RegExp(`^${PATTERN}$`);

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

/** True when middleware runs on `path` — i.e. a person must be signed in. */
const guarded = (path: string) => MATCHER.test(path);

test("the pages and the human APIs are behind sign-in", () => {
  for (const path of ["/", "/dev", "/ops/acme", "/api/tenants", "/api/admin/apps", "/api/audit", "/api/dlq/replay"]) {
    assert.ok(guarded(path), `${path} is not behind sign-in`);
  }
});

test("creating an intake is a person's act, behind sign-in", () => {
  assert.ok(guarded("/api/dev/intakes"));
});

test("pulling and consuming an intake authenticate by its token, not a sign-in", () => {
  assert.ok(!guarded("/api/dev/scaffold/42"));
  assert.ok(!guarded("/api/dev/scaffold/42/consume"));
});

test("each machine path that was already excluded still is", () => {
  for (const path of [
    "/api/sync/history",
    "/api/widget/status",
    "/api/audit/append",
    "/api/runs/ingest",
    "/api/dev/ingest",
    "/api/auth/login",
    "/_next/static/chunk.js",
    "/favicon.ico",
  ]) {
    assert.ok(!guarded(path), `${path} now requires a sign-in its callers cannot give`);
  }
});

test("a path that merely starts like an excluded one is still guarded", () => {
  // The anchor this list depends on. Without `(?:/|$)`, each of these would
  // skip sign-in by sharing a prefix.
  for (const path of [
    "/api/dev/scaffolding",
    "/api/dev/scaffold-admin",
    "/api/dev/ingestion",
    "/api/audit/appendix",
    "/api/syncing",
    "/api/widgetry",
    "/api/authz",
  ]) {
    assert.ok(guarded(path), `${path} skips sign-in by prefix`);
  }
});

test("the matcher this reads is the one Next is given", () => {
  // Guard on the guard: one exclusion per documented machine path, so a regex
  // that stopped parsing — or a second, unread matcher — fails here.
  assert.equal((SOURCE.match(/matcher:/g) ?? []).length, 1);
  // The literal, not MATCHER.source — RegExp escapes "/" in .source.
  assert.ok(PATTERN.includes("api/dev/scaffold(?:/|$)"));
});

console.log(`\n${passed} passed`);
