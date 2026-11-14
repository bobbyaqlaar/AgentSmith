// portal/test/signInPolicy.test.ts — multi-factor, lockout and session limits.
import assert from "node:assert/strict";
import { test } from "node:test";

import { basicSignIn, clearFailures, isLockedOut, LOCKOUT_SECONDS, MAX_FAILURES, mfaRefusal, recordFailure, signInAttempt, trackedCount } from "../lib/signInPolicy";
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

// ── The third pass: P3-R6 (.agent-rfc/designs/pass3-root-causes.md) ──
// Only accounts that exist are counted. R17, P2-R18 and P3-R6 were three patches to a map
// that held whatever name a caller sent; these are the attacks each of them failed.
let clock = 50_000_000;
const nextWindow = () => (clock += LOCKOUT_SECONDS * 1000 * 3);

test("a flood of invented names is never counted, and real users still sign in (P3-R6)", () => {
  const t = nextWindow();
  const before = trackedCount();
  for (let i = 0; i < 100_000; i++) signInAttempt(`invented-${t}-${i}`, false, false, t);
  assert.equal(trackedCount(), before);
  assert.deepEqual(signInAttempt(`alice-${t}`, true, true, t + 1000), { allowed: true, lockedNow: false });
});

test("guesses at a real account lock it, whatever floods around it (R17, P2-R18)", () => {
  const t = nextWindow();
  const admin = `admin-${t}`;
  for (let i = 0; i < MAX_FAILURES - 1; i++) signInAttempt(admin, true, false, t);
  for (let i = 0; i < 100_000; i++) signInAttempt(`noise-${t}-${i}`, false, false, t);
  assert.deepEqual(signInAttempt(admin, true, false, t), { allowed: false, lockedNow: true });
  assert.deepEqual(signInAttempt(admin, true, false, t), { allowed: false, lockedNow: false }); // audited once
});

test("a locked account is refused like a wrong password, even with the right one, until the window ends", () => {
  const t = nextWindow();
  const bob = `bob-${t}`;
  for (let i = 0; i < MAX_FAILURES; i++) signInAttempt(bob, true, false, t);
  const locked = signInAttempt(bob, true, true, t + 1000);
  const unknown = signInAttempt(`nobody-${t}`, false, false, t + 1000);
  assert.equal(locked.allowed, false);
  assert.equal(locked.allowed, unknown.allowed); // one answer: the lockout reveals no names
  assert.equal(signInAttempt(bob, true, true, t + LOCKOUT_SECONDS * 1000 + 2000).allowed, true);
});

// ── The decision the proxy answers with, driven through real headers (P3-R6) ──
const basic = (user: string, password: string) => "Basic " + Buffer.from(`${user}:${password}`).toString("base64");
function withEnv(env: Record<string, string | undefined>, fn: () => void) {
  const keys = ["OPS_PORTAL_USER", "OPS_PORTAL_PASSWORD", "OPS_PORTAL_USERS"];
  const saved = Object.fromEntries(keys.map((k) => [k, process.env[k]]));
  for (const k of keys) { if (env[k] === undefined) delete process.env[k]; else process.env[k] = env[k]; }
  try { fn(); } finally { for (const k of keys) { if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k]; } }
}
const MULTI = { OPS_PORTAL_USERS: JSON.stringify([{ username: "carol", password: "right", grants: [{ role: "operator", apps: "*" }] }]) };

for (const [mode, env, account, password] of [
  ["single-user", { OPS_PORTAL_USER: "solo", OPS_PORTAL_PASSWORD: "right" }, "solo", "right"],
  ["multi-user", MULTI, "carol", "right"],
] as const) {
  test(`${mode}: a header that is not Basic is not a sign-in`, () => withEnv(env, () => {
    assert.equal(basicSignIn(null), null);
    assert.equal(basicSignIn("Bearer x"), null);
  }));

  test(`${mode}: invented names are refused and never counted, and the account still signs in`, () => withEnv(env, () => {
    const before = trackedCount();
    for (let i = 0; i < 2000; i++) {
      const r = basicSignIn(basic(`invented-${mode}-${i}`, "guess"), 50_000);
      assert.equal(r?.granted, null);
      assert.equal(r?.lockedNow, false);
    }
    assert.equal(trackedCount(), before, "an invented name was counted");
    assert.ok(basicSignIn(basic(account, password), 50_000)?.granted, "the account was refused after a flood");
  }));

  test(`${mode}: wrong passwords lock the account once, and then the right one is refused too`, () => withEnv(env, () => {
    const t = 900_000_000;
    const locks = [];
    for (let i = 0; i < MAX_FAILURES; i++) locks.push(basicSignIn(basic(account, "wrong"), t)?.lockedNow);
    assert.deepEqual(locks, [...Array(MAX_FAILURES - 1).fill(false), true]);
    const locked = basicSignIn(basic(account, password), t);
    assert.equal(locked?.granted, null, "a locked account signed in");
    assert.equal(locked?.lockedNow, false, "the lock was reported twice");
    assert.ok(basicSignIn(basic(account, password), t + LOCKOUT_SECONDS * 1000 + 1)?.granted, "the lock did not end");
  }));
}

