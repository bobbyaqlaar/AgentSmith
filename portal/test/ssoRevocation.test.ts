/**
 * portal/test/ssoRevocation.test.ts — SSO_REVOCATION_MODE fail-open / fail-closed
 * (SEC-SSO-001).
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  checkSessionRevocation,
  interpretStatusResponse,
  resolveRevocationMode,
} from "../lib/ssoRevocationMode.ts";

const PORTAL = resolve(dirname(fileURLToPath(import.meta.url)), "..");

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

// ── What the ROUTE actually answers ─────────────────────────────────────────
//
// Everything above stubs `fetchStatus` and proves the decision function. That
// is not the same as proving the control, and the gap between them was real:
// /api/auth/session-status caught its database error and answered
// `200 {revoked: false}`, so the probe reported a healthy session and
// fail-closed allowed every request through the exact outage it exists for.
// The stubs all passed. These assert the reading of a real response.

test("a 5xx from the status route is not a verdict", () => {
  assert.deepEqual(interpretStatusResponse(503, { revoked: null, error: "db down" }), { ok: false });
  assert.deepEqual(interpretStatusResponse(500, null), { ok: false });
});

test("a 200 without a boolean verdict is not a verdict either", () => {
  // Belt and braces: even if the route regresses to answering 200 on an
  // error, an absent `revoked` must not be read as "not revoked".
  assert.deepEqual(interpretStatusResponse(200, {}), { ok: false });
  assert.deepEqual(interpretStatusResponse(200, { revoked: null }), { ok: false });
  assert.deepEqual(interpretStatusResponse(200, { revoked: "false" }), { ok: false });
});

test("a 200 with a verdict is one", () => {
  assert.deepEqual(interpretStatusResponse(200, { revoked: false }), { ok: true, revoked: false });
  assert.deepEqual(interpretStatusResponse(200, { revoked: true }), { ok: true, revoked: true });
});

test("fail-closed denies the outage the control exists for", async () => {
  // The full path, composed the way middleware composes it: the route is
  // unreachable/erroring, so the probe reports no verdict.
  const decision = await checkSessionRevocation({
    jti: "jti-1",
    mode: "fail-closed",
    fetchStatus: async () => interpretStatusResponse(503, { revoked: null, error: "db down" }),
  });
  assert.equal(decision, "unavailable");

  // ...and the default mode still behaves exactly as it always did.
  const legacy = await checkSessionRevocation({
    jti: "jti-1",
    mode: "fail-open",
    fetchStatus: async () => interpretStatusResponse(503, { revoked: null, error: "db down" }),
  });
  assert.equal(legacy, "allow");
});

test("the status route does not report an unreachable store as a healthy session", () => {
  // Reading the route, because nothing else here can: it needs a Next runtime
  // and a database. Narrow on purpose — it asserts the one thing that made the
  // control a no-op, rather than pretending to test the handler.
  const source = readFileSync(resolve(PORTAL, "app/api/auth/session-status/route.ts"), "utf8");
  const cat = source.slice(source.indexOf("} catch"));
  assert.ok(cat.includes("503"), "the catch path must answer 503, not a 2xx");
  assert.ok(
    !/status:\s*200/.test(cat),
    "the catch path must not answer 200 — middleware reads that as a verdict",
  );
});
