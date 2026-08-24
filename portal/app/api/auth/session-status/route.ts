// GET /api/auth/session-status?jti=... — internal endpoint middleware.ts
// calls (via fetch) to check the server-side revocation denylist
// (Product_Archive.md 4.14). Exists only because middleware.ts runs on
// the Edge runtime and can't use the `pg` driver directly — see
// lib/sessionRevocation.ts. Not itself gated by middleware.ts's auth check
// (this route only answers "is this opaque jti revoked", which reveals
// nothing about a tenant or identity on its own).
//
// WHERE THE FAIL-OPEN / FAIL-CLOSED DECISION LIVES: not here. This route
// reports what it knows, and `SSO_REVOCATION_MODE` decides what to do about
// not knowing (lib/ssoRevocationMode.ts, applied in middleware.ts).
//
// It used to catch a database error and answer `200 {revoked: false}` — "the
// session is fine" — which is a different fact from "I could not check".
// SEC-SSO-001's fail-closed mode reads a NON-OK response as unavailable, so a
// 200 meant the one failure fail-closed exists for, the revocation store being
// unreachable, still let every session through. The control was declared met,
// its test passed (it stubs the transport), and the snippet check found every
// string it looked for. Answering 503 is what makes the mode mean something;
// fail-open, still the default, treats it exactly as before.

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
    // 503, and `revoked: null` — absent, not false. A caller that ignores the
    // status code still cannot read this as "not revoked".
    return NextResponse.json(
      { revoked: null, error: `revocation store unreachable: ${String(err)}` },
      { status: 503 },
    );
  }
}
