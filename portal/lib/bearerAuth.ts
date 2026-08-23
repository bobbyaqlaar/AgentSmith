// portal/lib/bearerAuth.ts — one bearer-token gate for the machine-to-machine
// routes (/api/audit/append, /api/runs/ingest, /api/sync/history).
//
// Those three had the same twenty lines each, differing only by which env var
// holds the token and one noun in the error message — the shape that should be
// a parameter rather than a copy. Cloning it also meant the comparison had to
// be got right three times, and it was not: all three used `!==` on a secret.
//
// Distinct from lib/authz.ts, which gates HUMAN requests by role and tenant
// scope off headers the middleware sets. These callers are scripts and CI jobs
// with no session; conflating the two would put a token path inside the
// role-based helper where a future reader would not expect it.

import { NextResponse } from "next/server";
import { timingSafeEqual } from "node:crypto";

export interface BearerGateConfig {
  /** Env var holding the expected token, e.g. "OPS_PORTAL_SYNC_TOKEN". */
  envVar: string;
  /** What is disabled when the token is unset, e.g. "audit ingestion". */
  purpose: string;
}

/**
 * Returns a 4xx/5xx NextResponse when the request must be refused, or null when
 * it may proceed. Null means "authorised", so the caller reads:
 *
 *   const denied = requireBearer(request, { envVar: ..., purpose: ... });
 *   if (denied) return denied;
 */
export function requireBearer(
  request: Request,
  { envVar, purpose }: BearerGateConfig
): NextResponse | null {
  const expected = process.env[envVar];
  if (!expected) {
    // 503, not 401: the route is not misconfigured by the CALLER. Answering 401
    // would send an operator hunting for a bad token when the portal simply has
    // none configured.
    return NextResponse.json(
      { error: `${envVar} is not configured on the portal — ${purpose} is disabled.` },
      { status: 503 }
    );
  }

  const header = request.headers.get("authorization");
  if (!header || !constantTimeEquals(header, `Bearer ${expected}`)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  return null;
}

/**
 * Constant-time string comparison.
 *
 * `!==` on a secret leaks its length and, in principle, its prefix through
 * response timing. The window is small over HTTP and this is not the most
 * likely way in — but a correct comparison costs one function and removes the
 * question entirely, which is the better trade for an auth path.
 *
 * timingSafeEqual throws when the buffers differ in length, so the length check
 * comes first. That check is itself variable-time and unavoidably leaks length;
 * it is the content that matters here.
 */
function constantTimeEquals(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  if (bufA.length !== bufB.length) return false;
  return timingSafeEqual(bufA, bufB);
}
