// portal/lib/sessionToken.ts — the stateless signed-JWT session cookie
// (docs/DESIGN.md › Enterprise Install and Compliance Pack). Split out of lib/oidc.ts specifically so proxy.ts can
// import it directly. proxy.ts ran on the Edge runtime when this was split, and
// lib/oidc.ts imports `openid-client` at module scope, which is Node-only —
// importing oidc.ts from proxy.ts would pull openid-client into the
// Edge bundle and likely fail to build/run there. This module only uses
// `jose`, which is Edge-safe. See docs/PRODUCT_ARCHIVE.md 4.2: the original
// suggestion ("import verifySessionToken from lib/oidc.ts") would have hit
// exactly that problem, so the cookie name + verify/create logic moved here
// instead, with oidc.ts re-exporting them for the (Node-runtime) callback route.

import { SignJWT, jwtVerify } from "jose";

export const SESSION_COOKIE_NAME = "af_session";
export const SESSION_TTL_SECONDS = 8 * 60 * 60; // 8 hours

/** Idle and absolute limits, each its own setting (DESC ISR 5.2.3.6). With neither
 *  set, a session behaves as it always has: 8 hours, absolute. */
export function sessionLimits(env: Record<string, string | undefined> = process.env): { idleSeconds: number; absoluteSeconds: number } {
  const hours = Number(env.SESSION_ABSOLUTE_HOURS);
  const absoluteSeconds = Number.isFinite(hours) && hours > 0 ? Math.round(hours * 3600) : SESSION_TTL_SECONDS;
  const minutes = Number(env.SESSION_IDLE_MINUTES);
  const idleSeconds = Number.isFinite(minutes) && minutes > 0 ? Math.min(Math.round(minutes * 60), absoluteSeconds) : absoluteSeconds;
  return { idleSeconds, absoluteSeconds };
}

export interface OidcIdentity {
  sub: string;
  email?: string;
  name?: string;
}

// jti enables server-side revocation (docs/PRODUCT_ARCHIVE.md 4.14) without
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
  if (process.env.COMPLIANCE_PROFILE && secret.length < 32) {
    throw new Error("SSO_SESSION_SECRET must be at least 32 characters on a compliance profile.");
  }
  return new TextEncoder().encode(secret);
}

async function sign(identity: OidcIdentity, jti: string, absoluteAt: number, nowSeconds: number): Promise<string> {
  const { idleSeconds } = sessionLimits();
  return new SignJWT({ email: identity.email, name: identity.name, abs: absoluteAt })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(identity.sub)
    .setJti(jti)
    .setIssuedAt(nowSeconds)
    .setExpirationTime(Math.min(nowSeconds + idleSeconds, absoluteAt))
    .sign(sessionSecret());
}

export async function createSessionToken(identity: OidcIdentity, nowSeconds: number = Math.floor(Date.now() / 1000)): Promise<string> {
  return sign(identity, newJti(), nowSeconds + sessionLimits().absoluteSeconds, nowSeconds);
}

// How much of an idle window must be used before a request extends it, so a busy
// page does not sign a new cookie on every request.
const REFRESH_AFTER_SECONDS = 60;

/** A new token extending the idle window, or null when none is due. Keeps the
 *  jti, so a revocation still holds, and the absolute limit, which never moves. */
export async function refreshedSessionToken(session: VerifiedSession, nowSeconds: number = Math.floor(Date.now() / 1000)): Promise<string | null> {
  const { idleSeconds } = sessionLimits();
  if (!session.jti || !session.abs || !session.exp) return null;
  const target = Math.min(nowSeconds + idleSeconds, session.abs);
  if (target - session.exp < REFRESH_AFTER_SECONDS) return null;
  return sign(session, session.jti, session.abs, nowSeconds);
}

export interface VerifiedSession extends OidcIdentity {
  jti?: string;
  abs?: number;
  exp?: number;
}

export async function verifySessionToken(token: string): Promise<VerifiedSession | null> {
  try {
    const { payload } = await jwtVerify(token, sessionSecret());
    if (!payload.sub) return null;
    return {
      sub: payload.sub,
      email: typeof payload.email === "string" ? payload.email : undefined,
      abs: typeof payload.abs === "number" ? payload.abs : undefined,
      exp: typeof payload.exp === "number" ? payload.exp : undefined,
      name: typeof payload.name === "string" ? payload.name : undefined,
      jti: payload.jti,
    };
  } catch {
    return null;
  }
}

export function secureCookies(): boolean {
  return process.env.SSO_ALLOW_INSECURE_HTTP !== "true";
}
