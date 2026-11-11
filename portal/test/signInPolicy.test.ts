// portal/test/signInPolicy.test.ts — multi-factor, lockout and session limits.
import assert from "node:assert/strict";
import { test } from "node:test";

import { clearFailures, isLockedOut, LOCKOUT_SECONDS, MAX_FAILURES, mfaRefusal, recordFailure } from "../lib/signInPolicy";
import { createSessionToken, refreshedSessionToken, sessionLimits, verifySessionToken } from "../lib/sessionToken";

test("nothing asked, no profile: no refusal", () => assert.equal(mfaRefusal({}, {}), null));
test("a profile that asks nothing is refused", () => assert.ok(mfaRefusal({}, { COMPLIANCE_PROFILE: "dubai-gov" })));
test("amr satisfied", () => assert.equal(mfaRefusal({ amr: ["pwd", "mfa"] }, { SSO_REQUIRED_AMR: "mfa" }), null));
test("amr missing", () => assert.ok(mfaRefusal({ amr: ["pwd"] }, { SSO_REQUIRED_AMR: "mfa" })));
test("acr satisfied", () => assert.equal(mfaRefusal({ acr: "urn:mfa" }, { SSO_REQUIRED_ACR: "urn:mfa" }), null));

test("locks after the limit, and a success clears it", () => {
  const key = "u|ip";
  for (let i = 0; i < MAX_FAILURES - 1; i++) recordFailure(key, 1000);
  assert.equal(isLockedOut(key, 1000), false);
  recordFailure(key, 1000);
  assert.equal(isLockedOut(key, 1000), true);
  clearFailures(key);
  assert.equal(isLockedOut(key, 1000), false);
});
test("a lockout ends", () => {
  const key = "v|ip";
  for (let i = 0; i < MAX_FAILURES; i++) recordFailure(key, 1000);
  assert.equal(isLockedOut(key, 1000 + LOCKOUT_SECONDS * 1000 + 1), false);
});

test("defaults keep eight hours, absolute", () => assert.deepEqual(sessionLimits({}), { idleSeconds: 28800, absoluteSeconds: 28800 }));
test("idle cannot exceed absolute", () => {
  assert.deepEqual(sessionLimits({ SESSION_IDLE_MINUTES: "600", SESSION_ABSOLUTE_HOURS: "1" }), { idleSeconds: 3600, absoluteSeconds: 3600 });
});

test("activity extends idle, never absolute, and keeps the jti", async () => {
  process.env.SSO_SESSION_SECRET = "x".repeat(40);
  process.env.SESSION_IDLE_MINUTES = "15";
  process.env.SESSION_ABSOLUTE_HOURS = "1";
  const now = Math.floor(Date.now() / 1000);
  const first = (await verifySessionToken(await createSessionToken({ sub: "a" }, now)))!;
  assert.equal(first.exp, now + 900);
  assert.equal(first.abs, now + 3600);
  assert.equal(await refreshedSessionToken(first, now + 10), null, "not yet worth re-signing");
  const later = now + 600;
  const next = (await verifySessionToken((await refreshedSessionToken(first, later))!))!;
  assert.equal(next.exp, later + 900);
  assert.equal(next.abs, first.abs);
  assert.equal(next.jti, first.jti);
  const nearEnd = now + 3300;
  const capped = (await verifySessionToken((await refreshedSessionToken({ ...next, exp: nearEnd }, nearEnd))!))!;
  assert.equal(capped.exp, first.abs);
});

// ── The 4.1.0 release review: R17 ──
test("failures under other names never unlock a locked account (R17)", () => {
  const admin = "admin|ip";
  for (let i = 0; i < MAX_FAILURES; i++) recordFailure(admin, 1000);
  for (let i = 0; i < 10_001; i++) recordFailure(`invented-${i}|ip`, 1000);
  assert.equal(isLockedOut(admin, 1000), true);
  clearFailures(admin);
});
