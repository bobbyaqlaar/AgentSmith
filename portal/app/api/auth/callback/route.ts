// GET /api/auth/callback — OIDC redirect target (SPECS.md §30). Validates
// state + PKCE verifier from short-lived cookies, exchanges the code, sets
// the signed session cookie, and redirects back into the dashboard.

import { NextResponse } from "next/server";
import { cookies as nextCookies } from "next/headers";
import { getOidcSettings, handleCallback, createSessionToken, SESSION_COOKIE_NAME, secureCookies } from "@/lib/oidc";

export const dynamic = "force-dynamic"; // depends on query params (code/state) and request cookies — never cache

export async function GET(request: Request) {
  const settings = getOidcSettings();
  if (!settings) {
    return NextResponse.json({ error: "SSO is not enabled on this portal." }, { status: 404 });
  }

  const url = new URL(request.url);
  // Use next/headers' cookie jar, not manual header parsing — it correctly
  // URL-decodes values. A hand-rolled `cookieHeader.split(";")` parser was
  // tried first and shipped a real bug: it read back oidc_redirect_to's
  // percent-encoded "%2F" literally instead of decoding it to "/", so every
  // login landed on a 404 at .../%2F instead of the dashboard root.
  const cookieStore = await nextCookies();
  const expectedState = cookieStore.get("oidc_state")?.value;
  const codeVerifier = cookieStore.get("oidc_verifier")?.value;
  const redirectTo = cookieStore.get("oidc_redirect_to")?.value || "/";

  if (!expectedState || !codeVerifier) {
    return NextResponse.json({ error: "Missing OIDC state/verifier cookies — login flow expired or was tampered with." }, { status: 400 });
  }

  try {
    const identity = await handleCallback(settings, url, expectedState, codeVerifier);
    const sessionToken = await createSessionToken(identity);

    const res = NextResponse.redirect(new URL(redirectTo, url.origin));
    res.cookies.set(SESSION_COOKIE_NAME, sessionToken, {
      httpOnly: true,
      secure: secureCookies(),
      sameSite: "lax",
      maxAge: 8 * 60 * 60,
      path: "/",
    });
    res.cookies.delete("oidc_state");
    res.cookies.delete("oidc_verifier");
    res.cookies.delete("oidc_redirect_to");
    return res;
  } catch (err) {
    return NextResponse.json({ error: `OIDC callback failed: ${String(err)}` }, { status: 401 });
  }
}
