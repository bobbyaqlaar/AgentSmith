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

/**
 * Decide whether an SSO session may proceed given a session-status probe.
 *
 * - fail-open (default): unreachable status → allow (legacy behaviour)
 * - fail-closed: unreachable status → unavailable (middleware returns 503)
 */
export async function checkSessionRevocation(opts: {
  jti: string | undefined;
  mode: RevocationMode;
  fetchStatus: (jti: string) => Promise<{ ok: boolean; revoked?: boolean }>;
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
