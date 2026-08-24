// portal/lib/ssoRevocationMode.ts — SSO session-status fail-open / fail-closed
// (SEC-SSO-001, SPECS.md §30).

export type RevocationMode = "fail-open" | "fail-closed";

/** Outcome of a revocation probe used by middleware. */
export type RevocationDecision = "allow" | "deny" | "unavailable";

export function resolveRevocationMode(
  env: NodeJS.ProcessEnv = process.env
): RevocationMode {
  return env.SSO_REVOCATION_MODE === "fail-closed" ? "fail-closed" : "fail-open";
}

/** What a probe of /api/auth/session-status established. */
export interface ProbeResult {
  /** The store answered. False means "could not check", never "not revoked". */
  ok: boolean;
  revoked?: boolean;
}

/**
 * Read one session-status response. Shared by middleware's probe and the
 * tests, so both agree on what an answer IS.
 *
 * Two rules, and the second is the one that was missing:
 *
 *   * a non-2xx status is "could not check";
 *   * a 2xx whose body does not state a BOOLEAN `revoked` is also "could not
 *     check". `{revoked: null}` and `{}` are absences, and reading an absence
 *     as `false` is how the fail-closed mode came to allow every session
 *     through a database outage — the route answered 200 with no verdict and
 *     the caller supplied the reassuring one.
 *
 * Belt and braces on purpose: the route now answers 503 (see its header), and
 * if someone changes it back, this still refuses to invent a verdict.
 */
export function interpretStatusResponse(httpStatus: number, body: unknown): ProbeResult {
  if (httpStatus < 200 || httpStatus >= 300) return { ok: false };
  const revoked = (body as { revoked?: unknown } | null)?.revoked;
  if (typeof revoked !== "boolean") return { ok: false };
  return { ok: true, revoked };
}

/**
 * Decide whether an SSO session may proceed given a session-status probe.
 *
 * - fail-open (default): unreachable status → allow (legacy behaviour)
 * - fail-closed: unreachable status → unavailable (middleware returns 503)
 */
export async function checkSessionRevocation(opts: {
  jti: string | undefined;
  mode: RevocationMode;
  fetchStatus: (jti: string) => Promise<ProbeResult>;
}): Promise<RevocationDecision> {
  if (!opts.jti) return "allow";
  try {
    const res = await opts.fetchStatus(opts.jti);
    if (!res.ok) {
      return opts.mode === "fail-closed" ? "unavailable" : "allow";
    }
    return res.revoked === true ? "deny" : "allow";
  } catch {
    return opts.mode === "fail-closed" ? "unavailable" : "allow";
  }
}
