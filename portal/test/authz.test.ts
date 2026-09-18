// portal/test/authz.test.ts — cross-tenant isolation regression tests
// (docs/PRODUCT_ARCHIVE.md Part 3: "there is no test anywhere that asserts
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
  AREAS,
  GRANTS_HEADER,
  LEGACY_ROLES,
  PERMISSIONS,
  RETIRED_HEADERS,
  ROLES,
  ROLE_PERMISSIONS,
  SINGLE_USER_GRANTS,
  appsWith,
  areas,
  can,
  decodeGrantsHeader,
  encodeGrantsHeader,
  getAccessForSsoEmail,
  getAccessFromHeaderValue,
  parseGrants,
  roleFor,
  stripAccessHeaders,
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

const viewerOf = (...apps: string[]): Access => ({ grants: [{ role: "viewer", apps }] });

test("SECURITY: viewer scoped to tenant A cannot access tenant B", () => {
  const access = viewerOf("acme");
  assert.equal(can(access, "ops.read", "acme"), true);
  assert.equal(can(access, "ops.read", "globex"), false);
});

test("SECURITY: appsWith drops out-of-scope apps, not just hides UI", () => {
  assert.deepEqual(appsWith(viewerOf("acme"), "ops.read", ["acme", "globex", "initech"]), ["acme"]);
});

test("a grant over '*' covers every app", () => {
  const access: Access = { grants: [{ role: "administrator", apps: "*" }] };
  assert.equal(can(access, "ops.read", "anything"), true);
  assert.deepEqual(appsWith(access, "ops.read", ["a", "b"]), ["a", "b"]);
});

test("SECURITY: an SSO identity not in OPS_PORTAL_SSO_USERS gets no grants, not all", () => {
  delete process.env.OPS_PORTAL_SSO_USERS;
  const access = getAccessForSsoEmail("unknown@example.com");
  assert.deepEqual(access.grants, []);
  assert.equal(can(access, "ops.read", "acme"), false);
  assert.deepEqual(areas(access), []);
});

test("SSO identity listed in OPS_PORTAL_SSO_USERS gets its configured grants", () => {
  process.env.OPS_PORTAL_SSO_USERS = JSON.stringify([
    { email: "Ops@Example.com", grants: [{ role: "operator", apps: ["acme"] }] },
  ]);
  const access = getAccessForSsoEmail("ops@example.com"); // case-insensitive match
  assert.equal(can(access, "ops.dlq", "acme"), true);
  assert.equal(can(access, "ops.dlq", "globex"), false);
  delete process.env.OPS_PORTAL_SSO_USERS;
});

test("SECURITY: basic-auth credentials for tenant-A user do not grant tenant-B access", () => {
  process.env.OPS_PORTAL_USERS = JSON.stringify([
    { username: "acme-viewer", password: "correct-horse", role: "viewer", tenants: ["acme"] },
  ]);
  const access = verifyBasicAuthCredentials("acme-viewer", "correct-horse");
  assert.ok(access);
  assert.equal(can(access!, "ops.read", "acme"), true);
  assert.equal(can(access!, "ops.read", "globex"), false);
  delete process.env.OPS_PORTAL_USERS;
});

test("SECURITY: wrong password is rejected even for a real username", () => {
  process.env.OPS_PORTAL_USERS = JSON.stringify([
    { username: "acme-viewer", password: "correct-horse", role: "viewer", tenants: ["acme"] },
  ]);
  assert.equal(verifyBasicAuthCredentials("acme-viewer", "wrong"), null);
  delete process.env.OPS_PORTAL_USERS;
});

// ── Roles and permissions ────────────────────────────────────────────────────

test("the seven roles, and one legacy role accepted only from the old form", () => {
  assert.deepEqual([...ROLES], [
    "developer", "design_approver", "operator", "hitl_reviewer", "release_approver", "administrator", "super_user",
  ]);
  assert.deepEqual([...LEGACY_ROLES], ["viewer"]);
  for (const role of [...ROLES, ...LEGACY_ROLES]) {
    for (const permission of ROLE_PERMISSIONS[role]) assert.ok(PERMISSIONS.includes(permission), `${role}: ${permission}`);
  }
});

test("roles combine: Developer and Design approver on the same app, from one person", () => {
  const access = { grants: parseGrants({ grants: [
    { role: "developer", apps: ["acme"] }, { role: "design_approver", apps: ["acme"] },
  ] }) };
  assert.equal(can(access, "dev.approve", "acme"), true);
  assert.equal(can(access, "dev.allowlist", "acme"), true);
  assert.equal(can(access, "ops.read", "acme"), false);
});

test("a Developer may approve a deviation but not an allowlist entry", () => {
  const access = { grants: parseGrants({ grants: [{ role: "developer", apps: ["acme"] }] }) };
  assert.equal(can(access, "dev.approve", "acme"), true);
  assert.equal(can(access, "dev.allowlist", "acme"), false);
});

test("a HITL reviewer sees nothing else in Ops", () => {
  const access = { grants: parseGrants({ grants: [{ role: "hitl_reviewer", apps: ["acme"] }] }) };
  assert.equal(can(access, "ops.hitl", "acme"), true);
  assert.equal(can(access, "ops.read", "acme"), false);
  assert.equal(can(access, "ops.dlq", "acme"), false);
});

test("only a Super user holds organisation settings", () => {
  const admin = { grants: parseGrants({ grants: [{ role: "administrator", apps: "*" }] }) };
  const superUser = { grants: parseGrants({ grants: [{ role: "super_user", apps: "*" }] }) };
  assert.equal(can(admin, "admin.users"), true);
  assert.equal(can(admin, "admin.org"), false);
  assert.equal(can(superUser, "admin.org"), true);
});

test("SECURITY: an Administrator or Super user grant must cover every app", () => {
  assert.throws(() => parseGrants({ grants: [{ role: "administrator", apps: ["acme"] }] }), /whole organisation/);
  assert.throws(() => parseGrants({ grants: [{ role: "super_user", apps: [] }] }), /whole organisation/);
});

test("SECURITY: the legacy viewer role is not accepted in the new form", () => {
  assert.throws(() => parseGrants({ grants: [{ role: "viewer", apps: "*" }] }), /invalid role/);
  assert.throws(() => parseGrants({ grants: [{ role: "admin", apps: "*" }] }), /invalid role/);
});

// ── The old configuration grants exactly what it did ─────────────────────────

test("old `viewer` reads Ops, and nothing more", () => {
  const access = { grants: parseGrants({ role: "viewer", tenants: ["acme"] }) };
  assert.equal(can(access, "ops.read", "acme"), true);
  for (const p of PERMISSIONS.filter((p) => p !== "ops.read")) assert.equal(can(access, p, "acme"), false, p);
});

test("old `operator` keeps DLQ, widget minting and app settings — the old canWrite — within its tenants", () => {
  const access = { grants: parseGrants({ role: "operator", tenants: ["acme"] }) };
  for (const p of ["ops.read", "ops.dlq", "ops.widget", "ops.app_settings"] as const) {
    assert.equal(can(access, p, "acme"), true, p);
    assert.equal(can(access, p, "globex"), false, p);
  }
  assert.equal(can(access, "admin.audit"), false);
  assert.equal(can(access, "admin.apps", "acme"), false);
});

test("old `admin` is an Administrator over the tenants it listed", () => {
  const scoped = { grants: parseGrants({ role: "admin", tenants: ["acme"] }) };
  assert.equal(can(scoped, "admin.audit"), true);
  assert.equal(can(scoped, "admin.apps", "acme"), true);
  assert.equal(can(scoped, "admin.apps", "globex"), false, "a scoped admin stays scoped");
});

test("the single-user configuration is an Administrator on every app", () => {
  assert.deepEqual(SINGLE_USER_GRANTS, [{ role: "administrator", apps: "*" }]);
});

test("an unknown old role is refused, not defaulted", () => {
  assert.throws(() => parseGrants({ role: "superuser", tenants: "*" }), /invalid role/);
});

// ── Areas ────────────────────────────────────────────────────────────────────

test("the areas follow the permissions a user holds", () => {
  const dev = { grants: parseGrants({ grants: [{ role: "developer", apps: ["a"] }] }) };
  const ops = { grants: parseGrants({ grants: [{ role: "operator", apps: ["a"] }] }) };
  const admin = { grants: parseGrants({ grants: [{ role: "administrator", apps: "*" }] }) };
  assert.deepEqual(areas(dev), ["dev"]);
  assert.deepEqual(areas(ops), ["ops"]);
  assert.deepEqual(areas(admin), [...AREAS]);
});

// ── The trusted header ───────────────────────────────────────────────────────

test("SECURITY: a forged grants header decodes, but middleware.ts strips client copies before this is trusted", () => {
  // Asserting the decode shape here so a change to the header format cannot
  // silently widen access. See middleware.ts for the half that strips.
  const grants = [{ role: "operator", apps: ["acme", "a,b;c"] }] as const;
  assert.deepEqual(decodeGrantsHeader(encodeGrantsHeader([...grants].map((g) => ({ ...g, apps: [...g.apps] })))),
    [{ role: "operator", apps: ["acme", "a,b;c"] }]);
  assert.equal(GRANTS_HEADER, "x-af-grants");
  assert.deepEqual([...RETIRED_HEADERS], ["x-af-role", "x-af-tenant-scope"]);
});

test("SECURITY: an unknown role or malformed apps in the header is dropped, never widened", () => {
  const header = encodeURIComponent(JSON.stringify([
    { role: "god", apps: "*" }, { role: "operator", apps: "everything" }, { role: "viewer", apps: ["acme"] },
  ]));
  assert.deepEqual(decodeGrantsHeader(header), [{ role: "viewer", apps: ["acme"] }]);
});

test("SECURITY: every access header a client sends is stripped, retired names included", () => {
  const forged = new Headers({
    [GRANTS_HEADER]: encodeGrantsHeader([{ role: "super_user", apps: "*" }]),
    "x-af-role": "admin",
    "x-af-tenant-scope": "*",
    accept: "text/html",
  });
  const stripped = stripAccessHeaders(forged);
  for (const name of [GRANTS_HEADER, ...RETIRED_HEADERS]) assert.equal(stripped.get(name), null, name);
  assert.equal(stripped.get("accept"), "text/html", "only access headers are removed");
});

test("SECURITY: a role named after an Object.prototype property is not a role", () => {
  for (const role of ["constructor", "toString", "__proto__", "hasOwnProperty"]) {
    const header = encodeURIComponent(JSON.stringify([{ role, apps: "*" }]));
    assert.deepEqual(decodeGrantsHeader(header), [], role);
  }
});

test("the role recorded for an action is the one whose grant allowed it", () => {
  const access = { grants: parseGrants({ grants: [
    { role: "developer", apps: ["acme"] }, { role: "operator", apps: ["acme"] },
  ] }) };
  assert.equal(roleFor(access, "ops.dlq", "acme"), "operator");
  assert.equal(roleFor(access, "dev.approve", "acme"), "developer");
  assert.equal(roleFor(access, "ops.dlq", "globex"), undefined);
});

test("missing or unreadable grants header decodes to no grants (deny by default)", () => {
  assert.deepEqual(decodeGrantsHeader(null), []);
  assert.deepEqual(decodeGrantsHeader("%E0%A4%A"), []);
  assert.deepEqual(decodeGrantsHeader(encodeURIComponent("{}")), []);
  assert.deepEqual(getAccessFromHeaderValue(null), { grants: [] });
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
// WHICH APPS that human may act on — `can(access, permission, app)` for one app,
// `appsWith` for a list. An app-less `can(access, permission)` alone is a role
// check, and does not count. Machine-to-machine routes (requireBearer) are
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
      const scoped = /\bcan\(\s*access\s*,\s*"[\w.]+"\s*,/.test(handler.body) || handler.body.includes("appsWith(");
      assert.ok(
        scoped,
        `${handler.name} in ${file.replace(`${PORTAL_DIR}/`, "")} resolves Access but never ` +
          `scopes it to an app — a permission check with no app lets a user act on apps ` +
          `outside their grants`,
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
