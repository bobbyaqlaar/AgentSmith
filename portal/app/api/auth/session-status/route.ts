// GET /api/auth/session-status?jti=... — internal endpoint middleware.ts
// calls (via fetch) to check the server-side revocation denylist
// (Product_Archive.md 4.14). Exists only because middleware.ts runs on
// the Edge runtime and can't use the `pg` driver directly — see
// lib/sessionRevocation.ts. Not itself gated by middleware.ts's auth check
// (this route only answers "is this opaque jti revoked", which reveals
// nothing about a tenant or identity on its own).

import { NextResponse } from "next/server";
import { isSessionRevoked } from "@/lib/sessionRevocation";

export async function GET(request: Request) {
  const jti = new URL(request.url).searchParams.get("jti");
  if (!jti) {
    return NextResponse.json({ error: "jti query param is required" }, { status: 400 });
  }
  try {
    const revoked = await isSessionRevoked(jti);
    return NextResponse.json({ revoked });
  } catch (err) {
    // Fail open: an unreachable DB here must not lock out every SSO user —
    // same "never block on this check's own availability" philosophy as
    // _ai_audit_log_event in install-ai-stack.sh. The 8h token TTL already
    // bounds how long a missed revocation can matter.
    return NextResponse.json({ revoked: false, error: String(err) }, { status: 200 });
  }
}
