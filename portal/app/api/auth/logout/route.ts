import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE_NAME } from "@/lib/oidc";
import { verifySessionToken } from "@/lib/sessionToken";
import { revokeSession } from "@/lib/sessionRevocation";

export async function POST(request: Request) {
  // Revoke server-side (not just delete the cookie client-side) so a copy of
  // this token leaked/cached elsewhere stops working immediately instead of
  // remaining valid for the rest of its 8h TTL (FIXES_AND_CLEANUP.md 4.14).
  const token = cookies().get(SESSION_COOKIE_NAME)?.value;
  if (token) {
    const session = await verifySessionToken(token);
    if (session?.jti) {
      await revokeSession(session.jti);
    }
  }

  const res = NextResponse.redirect(new URL("/", request.url));
  res.cookies.delete(SESSION_COOKIE_NAME);
  return res;
}
