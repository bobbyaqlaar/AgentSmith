// portal/test/authz.test.ts — cross-tenant isolation regression tests
// (Product_Archive.md Part 3: "there is no test anywhere that asserts
// tenant A's session/token/gateway instance cannot read tenant B's data").
//
// Run (from portal/):
//   node --experimental-strip-types \
//     --experimental-loader=./test/ts-extension-loader.mjs \
//     test/authz.test.ts
//
// THE LOADER IS REQUIRED. lib/ modules import each other with
// extensionless relative specifiers, which bare type-stripping cannot
// resolve. Every invocation in this repo passes it — see
// scripts/test/test_ts_runner_invocations.py, which enforces that.
// Plain node:assert, no framework dependency — mirrors
// templates/in-app-widget/test/widget.test.mjs.

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  canAccessTenant,
  canAdmin,
  canWrite,
  decodeTenantScopeHeader,
  encodeTenantScopeHeader,
  filterTenantIds,
  getAccessFromHeaderValues,
  getAccessForSsoEmail,
  verifyBasicAuthCredentials,
  type Access,
} from "../lib/authz.ts";

const PORTAL_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");

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

test("SECURITY: viewer scoped to tenant A cannot access tenant B", () => {
  const access: Access = { role: "viewer", tenantScope: ["acme"] };
  assert.equal(canAccessTenant(access, "acme"), true);
  assert.equal(canAccessTenant(access, "globex"), false);
});

test("SECURITY: filterTenantIds drops out-of-scope tenants, not just hides UI", () => {
  const access: Access = { role: "viewer", tenantScope: ["acme"] };
  const visible = filterTenantIds(access, ["acme", "globex", "initech"]);
  assert.deepEqual(visible, ["acme"]);
});

test("admin/operator with tenantScope '*' sees every tenant", () => {
  const access: Access = { role: "admin", tenantScope: "*" };
  assert.equal(canAccessTenant(access, "anything"), true);
  assert.deepEqual(filterTenantIds(access, ["a", "b"]), ["a", "b"]);
});

test("SECURITY: an SSO identity not in OPS_PORTAL_SSO_USERS gets zero tenants, not all", () => {
  delete process.env.OPS_PORTAL_SSO_USERS;
  const access = getAccessForSsoEmail("unknown@example.com");
  assert.equal(access.role, "viewer");
  assert.deepEqual(access.tenantScope, []);
  assert.equal(canAccessTenant(access, "acme"), false);
});

test("SSO identity listed in OPS_PORTAL_SSO_USERS gets its configured scope", () => {
  process.env.OPS_PORTAL_SSO_USERS = JSON.stringify([
    { email: "Ops@Example.com", role: "operator", tenants: ["acme"] },
  ]);
  const access = getAccessForSsoEmail("ops@example.com"); // case-insensitive match
  assert.equal(access.role, "operator");
  assert.deepEqual(access.tenantScope, ["acme"]);
  assert.equal(canAccessTenant(access, "acme"), true);
  assert.equal(canAccessTenant(access, "globex"), false);
  delete process.env.OPS_PORTAL_SSO_USERS;
});

test("SECURITY: basic-auth credentials for tenant-A user do not grant tenant-B access", () => {
  process.env.OPS_PORTAL_USERS = JSON.stringify([
    { username: "acme-viewer", password: "correct-horse", role: "viewer", tenants: ["acme"] },
  ]);
  const access = verifyBasicAuthCredentials("acme-viewer", "correct-horse");
  assert.ok(access);
  assert.equal(canAccessTenant(access!, "acme"), true);
  assert.equal(canAccessTenant(access!, "globex"), false);
  delete process.env.OPS_PORTAL_USERS;
});

test("SECURITY: wrong password is rejected even for a real username", () => {
  process.env.OPS_PORTAL_USERS = JSON.stringify([
    { username: "acme-viewer", password: "correct-horse", role: "viewer", tenants: ["acme"] },
  ]);
  assert.equal(verifyBasicAuthCredentials("acme-viewer", "wrong"), null);
  delete process.env.OPS_PORTAL_USERS;
});

test("SECURITY: a forged x-af-role/x-af-tenant-scope header decodes, but middleware.ts strips client copies before this is trusted", () => {
  // This module only documents the *decode* half — see middleware.ts's
  // stripForgedAccessHeaders for the half that makes trusting these headers
  // safe in route handlers. Asserting the decode shape here so a future
  // change to the header format doesn't silently widen access.
  const access = getAccessFromHeaderValues("admin", "*");
  assert.equal(access.role, "admin");
  assert.equal(access.tenantScope, "*");

  const scoped = getAccessFromHeaderValues("viewer", "acme,globex");
  assert.deepEqual(scoped.tenantScope, ["acme", "globex"]);
});

test("unrecognized role header value falls back to viewer, not admin", () => {
  const access = getAccessFromHeaderValues("superuser", "*");
  assert.equal(access.role, "viewer");
});

test("missing tenant-scope header decodes to empty scope (deny-by-default), not '*'", () => {
  assert.deepEqual(decodeTenantScopeHeader(null), []);
});

test("encode/decode tenant scope round-trips", () => {
  assert.equal(decodeTenantScopeHeader(encodeTenantScopeHeader("*")), "*");
  assert.deepEqual(decodeTenantScopeHeader(encodeTenantScopeHeader(["a", "b"])), ["a", "b"]);
});

test("canWrite/canAdmin role gates", () => {
  assert.equal(canWrite({ role: "viewer", tenantScope: "*" }), false);
  assert.equal(canWrite({ role: "operator", tenantScope: "*" }), true);
  assert.equal(canWrite({ role: "admin", tenantScope: "*" }), true);
  assert.equal(canAdmin({ role: "operator", tenantScope: "*" }), false);
  assert.equal(canAdmin({ role: "admin", tenantScope: "*" }), true);
});

// ── Every RBAC route scopes to a tenant ─────────────────────────────────────
//
// The rule the routes are supposed to follow, checked over the routes rather
// than trusted. It was NOT followed: POST /api/tenants gated on the role and
// not the scope, so an operator scoped to one tenant could upsert ANOTHER
// tenant's row — its name, its isolation, its budget cap, and the replay
// webhook URL and secret the portal signs outgoing payloads with. Both DLQ
// actions, both widget-token actions and every tenant read had the check; the
// one route that creates and overwrites tenants did not.
//
// The invariant: a handler that resolves a human's Access must also decide
// WHICH TENANTS that human may act on — `canAccessTenant` for a single tenant,
// `filterTenantIds` for a list. Machine-to-machine routes (requireBearer) are
// out of scope by construction: they have no Access to scope.

function routeFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...routeFiles(full));
    else if (entry.name === "route.ts") out.push(full);
  }
  return out;
}

/**
 * One route file, split into its exported HTTP handlers.
 *
 * Per handler, not per file — and that distinction is not hypothetical. The
 * first version of this check tested whole files, and when the missing scope
 * check was deleted from POST /api/tenants again to see the test fail, it
 * PASSED: the GET handler in the same file calls `filterTenantIds`, which
 * satisfied a file-level rule while the mutating handler had no check at all.
 * A sweep that cannot fail for the defect it was written for is the finding.
 */
function handlers(source: string): Array<{ name: string; body: string }> {
  const pattern = /export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b/g;
  const starts = [...source.matchAll(pattern)];
  return starts.map((m, i) => ({
    name: m[1],
    body: source.slice(m.index!, i + 1 < starts.length ? starts[i + 1].index! : source.length),
  }));
}

test("every HANDLER that reads an operator's Access also scopes it to tenants", () => {
  const routes = routeFiles(join(PORTAL_DIR, "app", "api"));
  // Without this the loop below could pass over an empty list — the failure
  // mode the middleware import-graph walker already shipped once.
  assert.ok(routes.length >= 10, `expected the API tree to have routes, found ${routes.length}`);

  let checked = 0;
  for (const file of routes) {
    for (const handler of handlers(readFileSync(file, "utf8"))) {
      if (!handler.body.includes("currentAccess(")) continue; // machine-to-machine
      checked += 1;
      assert.ok(
        handler.body.includes("canAccessTenant") || handler.body.includes("filterTenantIds"),
        `${handler.name} in ${file.replace(`${PORTAL_DIR}/`, "")} resolves Access but never ` +
          `scopes it to a tenant — a role check alone lets an operator act on tenants ` +
          `outside its own scope`,
      );
    }
  }
  assert.ok(checked >= 8, `expected several RBAC handlers, examined ${checked} — the split is broken, not the routes`);
});

// ── No secret is compared with === ──────────────────────────────────────────
//
// The multi-user path was made constant-time and the single-user fallback in
// middleware.ts — the DEFAULT configuration — kept `reqPass === pass` for
// three more months. This is that fix, made permanent: a grep, run every time,
// over the files where a credential comparison can appear.

const CREDENTIAL_COMPARE = /(?:pass|password|secret|token)\w*\s*[!=]==(?!=)\s*(?!undefined\b|null\b)|[!=]==(?!=)\s*\w*(?:pass|password|secret|token)\b/i;

test("no credential is compared with === or !==", () => {
  const files = [
    "middleware.ts",
    "lib/authz.ts",
    "lib/bearerAuth.ts",
    "lib/sessionToken.ts",
    "lib/widgetTokens.ts",
  ];
  let scanned = 0;
  for (const rel of files) {
    const source = readFileSync(join(PORTAL_DIR, rel), "utf8")
      // Comments stripped, because this file and those explain the rule in
      // prose — the same trap test/edgeSafety.test.ts documents, where a guard
      // fired on the sentence describing what it guards.
      .replace(/^\s*\/\/.*$/gm, "")
      .replace(/\/\*[\s\S]*?\*\//g, "");
    scanned += 1;
    for (const line of source.split("\n")) {
      assert.ok(
        !CREDENTIAL_COMPARE.test(line),
        `${rel}: \`${line.trim()}\` compares a credential with ===/!== — use ` +
          `constantTimeEquals from lib/constantTime`,
      );
    }
  }
  assert.equal(scanned, files.length, "the scan did not read every file it names");
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
