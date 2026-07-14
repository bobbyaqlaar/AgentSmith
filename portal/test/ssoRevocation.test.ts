/**
 * portal/test/ssoRevocation.test.ts — SSO_REVOCATION_MODE fail-open / fail-closed
 * (SEC-SSO-001).
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  checkSessionRevocation,
  resolveRevocationMode,
} from "../lib/ssoRevocationMode.ts";

test("resolveRevocationMode defaults to fail-open", () => {
  assert.equal(resolveRevocationMode({}), "fail-open");
  assert.equal(resolveRevocationMode({ SSO_REVOCATION_MODE: "fail-open" }), "fail-open");
  assert.equal(resolveRevocationMode({ SSO_REVOCATION_MODE: "weird" }), "fail-open");
});

test("resolveRevocationMode accepts fail-closed", () => {
  assert.equal(
    resolveRevocationMode({ SSO_REVOCATION_MODE: "fail-closed" }),
    "fail-closed"
  );
});

test("fail-open allows when session-status unreachable", async () => {
  const decision = await checkSessionRevocation({
    jti: "jti-1",
    mode: "fail-open",
    fetchStatus: async () => {
      throw new Error("ECONNREFUSED");
    },
  });
  assert.equal(decision, "allow");
});

test("fail-closed returns unavailable when session-status unreachable", async () => {
  const decision = await checkSessionRevocation({
    jti: "jti-1",
    mode: "fail-closed",
    fetchStatus: async () => {
      throw new Error("ECONNREFUSED");
    },
  });
  assert.equal(decision, "unavailable");
});

test("fail-closed returns unavailable on non-ok HTTP status", async () => {
  const decision = await checkSessionRevocation({
    jti: "jti-1",
    mode: "fail-closed",
    fetchStatus: async () => ({ ok: false }),
  });
  assert.equal(decision, "unavailable");
});

test("revoked jti is deny in both modes", async () => {
  for (const mode of ["fail-open", "fail-closed"] as const) {
    const decision = await checkSessionRevocation({
      jti: "jti-revoked",
      mode,
      fetchStatus: async () => ({ ok: true, revoked: true }),
    });
    assert.equal(decision, "deny", mode);
  }
});

test("active jti is allow in both modes", async () => {
  for (const mode of ["fail-open", "fail-closed"] as const) {
    const decision = await checkSessionRevocation({
      jti: "jti-ok",
      mode,
      fetchStatus: async () => ({ ok: true, revoked: false }),
    });
    assert.equal(decision, "allow", mode);
  }
});
