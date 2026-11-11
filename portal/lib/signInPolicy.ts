// portal/lib/signInPolicy.ts — what a sign-in must prove, and the limit on failed
// ones. Pure enough to test without Next.

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
const failures = new Map<string, { count: number; first: number }>();
const MAX_TRACKED = 10_000;

export function isLockedOut(key: string, now: number = Date.now()): boolean {
  const entry = failures.get(key);
  if (!entry) return false;
  if (now - entry.first > LOCKOUT_SECONDS * 1000) {
    failures.delete(key);
    return false;
  }
  return entry.count >= MAX_FAILURES;
}

/** Make room: expired entries first, then the oldest that is not locked. Never a lock. */
function evict(now: number): void {
  for (const [key, entry] of failures) {
    if (now - entry.first > LOCKOUT_SECONDS * 1000) failures.delete(key);
  }
  for (const [key, entry] of failures) {
    if (failures.size < MAX_TRACKED) return;
    if (entry.count < MAX_FAILURES) failures.delete(key);
  }
}

export function recordFailure(key: string, now: number = Date.now()): void {
  const entry = failures.get(key);
  if (entry && now - entry.first <= LOCKOUT_SECONDS * 1000) {
    entry.count += 1;
    return;
  }
  if (failures.size >= MAX_TRACKED) evict(now);
  // At the cap with every entry locked, a new name is not tracked rather than a lock
  // being dropped: clearing the map unlocked every account (the 4.1.0 release review, R17).
  if (failures.size < MAX_TRACKED) failures.set(key, { count: 1, first: now });
}

export function clearFailures(key: string): void {
  failures.delete(key);
}
