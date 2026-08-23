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
import { constantTimeEquals } from "./constantTime";

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
