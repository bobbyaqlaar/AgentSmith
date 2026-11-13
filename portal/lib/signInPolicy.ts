// portal/lib/signInPolicy.ts — what a sign-in must prove, and the limit on failed
// ones. Pure enough to test without Next.

import { SINGLE_USER_GRANTS, isBasicAccount, verifyBasicAuthCredentials, type Grant } from "./authz";
import { constantTimeEquals } from "./constantTime";

function list(value: string | undefined): string[] {
  return (value ?? "").split(",").map((v) => v.trim()).filter(Boolean);
}

/** Why this identity token does not prove multi-factor, or null when it does or
 *  when nothing asks it to. A compliance profile must ask. */
export function mfaRefusal(claims: Record<string, unknown>, env: Record<string, string | undefined> = process.env): string | null {
  const amr = list(env.SSO_REQUIRED_AMR);
  const acr = list(env.SSO_REQUIRED_ACR);
  if (amr.length === 0 && acr.length === 0) {
    return env.COMPLIANCE_PROFILE ? "a compliance profile requires SSO_REQUIRED_AMR or SSO_REQUIRED_ACR, so multi-factor can be checked" : null;
  }
  const given = Array.isArray(claims.amr) ? claims.amr.map(String) : [];
  if (amr.some((m) => given.includes(m)) || (typeof claims.acr === "string" && acr.includes(claims.acr))) return null;
  return "the identity provider did not report multi-factor authentication for this sign-in";
}

export const MAX_FAILURES = 5;
export const LOCKOUT_SECONDS = 900;

// Per process: a cluster of N instances allows up to N times this, which is
// still a limit. SSO deployments rely on the identity provider's own lockout.
//
// Only accounts that exist are counted (the 4.1.0 review's third pass, P3-R6). The map
// held whatever name a caller sent, so every bound on it was a flood target: R17 evicted
// unlocked entries (a flood reset `admin`), P2-R18 refused names a full map could not
// hold (a flood locked out every user). Keyed by real accounts, it is as large as the
// account list and nothing a caller sends can fill it.
const failures = new Map<string, { count: number; first: number }>();
const WINDOW_MS = LOCKOUT_SECONDS * 1000;

export function isLockedOut(account: string, now: number = Date.now()): boolean {
  const entry = failures.get(account);
  if (!entry) return false;
  if (now - entry.first > WINDOW_MS) {
    failures.delete(account);
    return false;
  }
  return entry.count >= MAX_FAILURES;
}

export function recordFailure(account: string, now: number = Date.now()): void {
  const entry = failures.get(account);
  if (entry && now - entry.first <= WINDOW_MS) entry.count += 1;
  else failures.set(account, { count: 1, first: now });
}

/** One HTTP Basic sign-in, decided. `isAccount` is whether the name has an account; a name
 *  that has none is refused and never counted. A locked account is refused exactly as a
 *  wrong password is, so the lockout does not tell a caller which names exist. `lockedNow`
 *  is true on the failure that locks the account, once, for the audit log. */
export function signInAttempt(name: string, isAccount: boolean, passwordOk: boolean, now: number = Date.now()):
    { allowed: boolean; lockedNow: boolean } {
  if (!isAccount) return { allowed: false, lockedNow: false };
  if (isLockedOut(name, now)) return { allowed: false, lockedNow: false };
  if (passwordOk) {
    clearFailures(name);
    return { allowed: true, lockedNow: false };
  }
  recordFailure(name, now);
  return { allowed: false, lockedNow: isLockedOut(name, now) };
}

/** How many names the lockout holds: never more than the accounts that failed. */
export function trackedCount(): number {
  return failures.size;
}

export function clearFailures(key: string): void {
  failures.delete(key);
}

/** An HTTP Basic `Authorization` header, decided: who it signs in as, if anyone, and whether
 *  this failure locked the account. Null when the header is not Basic. The proxy only turns
 *  this into a response; the decision lives here so a test can drive it (proxy.ts imports Next).
 *  OPS_PORTAL_USERS (per-user grants) takes precedence; otherwise the single
 *  OPS_PORTAL_USER/PASSWORD, an Administrator on every app. Both compare in constant time,
 *  and both comparisons run before either is read, so neither short-circuits the other. */
export function basicSignIn(authorization: string | null, now: number = Date.now()):
    { user: string; granted: { grants: Grant[]; actor: string | null } | null; lockedNow: boolean } | null {
  if (!authorization?.startsWith("Basic ")) return null;
  const decoded = Buffer.from(authorization.slice(6), "base64").toString("utf-8");
  const sep = decoded.indexOf(":");
  const user = sep === -1 ? decoded : decoded.slice(0, sep);
  const password = sep === -1 ? "" : decoded.slice(sep + 1);
  let granted: { grants: Grant[]; actor: string | null } | null = null;
  let isAccount: boolean;
  if (!process.env.OPS_PORTAL_USERS) {
    const userOk = constantTimeEquals(process.env.OPS_PORTAL_USER ?? "", user);
    const passOk = constantTimeEquals(process.env.OPS_PORTAL_PASSWORD ?? "", password);
    // The proxy answers 500 before this when either is unset.
    isAccount = userOk && !!process.env.OPS_PORTAL_USER;
    if (isAccount && passOk && process.env.OPS_PORTAL_PASSWORD) granted = { grants: SINGLE_USER_GRANTS, actor: user };
  } else {
    const access = verifyBasicAuthCredentials(user, password);
    isAccount = isBasicAccount(user);
    if (access) granted = { grants: access.grants, actor: access.actor };
  }
  const attempt = signInAttempt(user, isAccount, granted !== null, now);
  return { user, granted: attempt.allowed ? granted : null, lockedNow: attempt.lockedNow };
}
