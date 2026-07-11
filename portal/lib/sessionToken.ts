// portal/lib/sessionToken.ts — the stateless signed-JWT session cookie
// (SPECS.md §30). Split out of lib/oidc.ts specifically so middleware.ts can
// import it directly: middleware.ts runs on the Edge runtime by default, and
// lib/oidc.ts imports `openid-client` at module scope, which is Node-only —
// importing oidc.ts from middleware.ts would pull openid-client into the
// Edge bundle and likely fail to build/run there. This module only uses
// `jose`, which is Edge-safe. See Product_Archive.md 4.2: the original
// suggestion ("import verifySessionToken from lib/oidc.ts") would have hit
// exactly that problem, so the cookie name + verify/create logic moved here
// instead, with oidc.ts re-exporting them for the (Node-runtime) callback route.

import { SignJWT, jwtVerify } from "jose";

export const SESSION_COOKIE_NAME = "af_session";
export const SESSION_TTL_SECONDS = 8 * 60 * 60; // 8 hours

export interface OidcIdentity {
  sub: string;
  email?: string;
  name?: string;
}

// jti enables server-side revocation (Product_Archive.md 4.14) without
// needing the full token: logout records this id in revoked_sessions
// (portal/db/schema.sql) instead of the (much larger, and itself sensitive)
// signed token string.
function newJti(): string {
  return crypto.randomUUID();
}

function sessionSecret(): Uint8Array {
  const secret = process.env.SSO_SESSION_SECRET;
  if (!secret) {
    throw new Error("SSO_SESSION_SECRET is not set — required whenever SSO_ENABLED=true.");
  }
  return new TextEncoder().encode(secret);
}

export async function createSessionToken(identity: OidcIdentity): Promise<string> {
  return new SignJWT({ email: identity.email, name: identity.name })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(identity.sub)
    .setJti(newJti())
    .setIssuedAt()
    .setExpirationTime(`${SESSION_TTL_SECONDS}s`)
    .sign(sessionSecret());
}

export interface VerifiedSession extends OidcIdentity {
  jti?: string;
}

export async function verifySessionToken(token: string): Promise<VerifiedSession | null> {
  try {
    const { payload } = await jwtVerify(token, sessionSecret());
    if (!payload.sub) return null;
    return {
      sub: payload.sub,
      email: typeof payload.email === "string" ? payload.email : undefined,
      name: typeof payload.name === "string" ? payload.name : undefined,
      jti: payload.jti,
    };
  } catch {
    return null;
  }
}
