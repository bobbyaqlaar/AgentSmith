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
//
// A live count is never dropped: an entry leaves only when its window has passed.
// Evicting at a cap let a flood of invented names reset `admin` before its fifth
// guess, and a name the full map could not hold was guessed without limit (the 4.1.0
// review's second pass, P2-R18). So a name the map cannot count is refused: the
// lockout fails closed. The cost, stated: about 110 failed sign-ins a second for
// fifteen minutes on one process refuses new names there until entries expire.
const failures = new Map<string, { count: number; first: number }>();
export const MAX_TRACKED = 100_000;
const WINDOW_MS = LOCKOUT_SECONDS * 1000;
let prunedAt = -Infinity;

/** Drop expired entries. The map keeps insertion order and an entry is re-inserted
 *  when its window restarts, so the expired ones are at the front. At most once a
 *  second, so a flood cannot make every request walk the map. */
function prune(now: number): void {
  if (now - prunedAt < 1000) return;
  prunedAt = now;
  for (const [key, entry] of failures) {
    if (now - entry.first <= WINDOW_MS) return;
    failures.delete(key);
  }
}

export function isLockedOut(key: string, now: number = Date.now()): boolean {
  const entry = failures.get(key);
  if (entry) {
    if (now - entry.first > WINDOW_MS) {
      failures.delete(key);
      return false;
    }
    return entry.count >= MAX_FAILURES;
  }
  if (failures.size < MAX_TRACKED) return false;
  prune(now);
  return failures.size >= MAX_TRACKED; // could not be counted, so not let through
}

export function recordFailure(key: string, now: number = Date.now()): void {
  const entry = failures.get(key);
  if (entry && now - entry.first <= WINDOW_MS) {
    entry.count += 1;
    return;
  }
  failures.delete(key); // an expired entry starts again at the back
  if (failures.size >= MAX_TRACKED) prune(now);
  if (failures.size < MAX_TRACKED) failures.set(key, { count: 1, first: now });
}

export function clearFailures(key: string): void {
  failures.delete(key);
}
