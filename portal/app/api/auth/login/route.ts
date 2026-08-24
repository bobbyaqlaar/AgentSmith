// GET /api/auth/login — starts the OIDC authorization-code+PKCE flow
// (SPECS.md §30). Only meaningful when SSO_ENABLED=true.

import { NextResponse } from "next/server";
import { getOidcSettings, buildAuthorizationUrl, secureCookies } from "@/lib/oidc";
import { safeRedirectPath } from "@/lib/safeUrl";

export const dynamic = "force-dynamic"; // fresh state/PKCE verifier every request — must never be statically cached

export async function GET(request: Request) {
  const settings = getOidcSettings();
  if (!settings) {
    return NextResponse.json({ error: "SSO is not enabled on this portal (SSO_ENABLED != true)." }, { status: 404 });
  }

  const { url, state, codeVerifier } = await buildAuthorizationUrl(settings);

  const res = NextResponse.redirect(url);
  // Short-lived, httpOnly cookies — only needed for the duration of the
  // redirect round-trip to the OIDC provider and back.
  const cookieOpts = {
    httpOnly: true,
    secure: secureCookies(),
    sameSite: "lax" as const,
    maxAge: 600,
    path: "/",
  };
  res.cookies.set("oidc_state", state, cookieOpts);
  res.cookies.set("oidc_verifier", codeVerifier, cookieOpts);

  // Checked HERE as well as at the point of use, so a destination that would
  // leave the origin never reaches the cookie in the first place. See
  // lib/safeRedirectPath: the old `startsWith("/")` accepted `//evil.example`.
  const requestUrl = new URL(request.url);
  const redirectTo = safeRedirectPath(requestUrl.searchParams.get("redirect_to"), requestUrl.origin);
  if (redirectTo) {
    res.cookies.set("oidc_redirect_to", redirectTo, cookieOpts);
  }

  return res;
}
