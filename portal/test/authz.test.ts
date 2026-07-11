// portal/test/authz.test.ts — cross-tenant isolation regression tests
// (Product_Archive.md Part 3: "there is no test anywhere that asserts
// tenant A's session/token/gateway instance cannot read tenant B's data").
//
// Run: node --experimental-strip-types test/authz.test.ts (from portal/),
// same runner pattern as package.json's db:migrate script. Plain
// node:assert, no framework dependency — mirrors
// templates/in-app-widget/test/widget.test.mjs.

import assert from "node:assert/strict";
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

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
