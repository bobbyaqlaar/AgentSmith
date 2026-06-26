// portal/lib/oidc.ts — SSO/OIDC for the Ops Portal (SPECS.md §30, enterprise pack).
//
// "When enterprise pack is enabled: Ops Portal requires SSO login (OIDC)."
// This replaces (not augments) HTTP basic auth for the dashboard when
// SSO_ENABLED=true — see middleware.ts. The machine-to-machine endpoints
// (/api/sync/*, /api/widget/*, /api/audit/append) are unaffected either way;
// they were never gated by basic auth and aren't gated by SSO either.
//
// Session model: a stateless, HMAC-signed JWT cookie (HS256, jose), not a
// server-side session store — consistent with the rest of this app's
// signed-token pattern (widget tokens, sync tokens). No new infra dependency.

import * as client from "openid-client";
import {
  SESSION_COOKIE_NAME,
  SESSION_TTL_SECONDS,
  createSessionToken,
  verifySessionToken,
  type OidcIdentity as SessionIdentity,
} from "./sessionToken";

// Re-exported for existing callers of this module (app/api/auth/* routes,
// which run on the Node runtime and can safely import oidc.ts in full) —
// see lib/sessionToken.ts for why the implementation itself lives there now.
export { SESSION_COOKIE_NAME, SESSION_TTL_SECONDS, createSessionToken, verifySessionToken };

// Cookie Secure flag, tied to the SAME explicit opt-in as the OIDC insecure-
// HTTP allowance — NOT to NODE_ENV. `next start` sets NODE_ENV=production
// unconditionally regardless of whether TLS is actually present, so an
// inferred check there incorrectly marks cookies Secure during legitimate
// local-HTTP dev/test runs, and browsers/HTTP clients then correctly refuse
// to send them back over plain HTTP — silently breaking the entire login
// flow with no helpful error. One explicit flag governs both behaviors.
export function secureCookies(): boolean {
  return process.env.SSO_ALLOW_INSECURE_HTTP !== "true";
}

export interface OidcSettings {
  issuer: string;
  clientId: string;
  clientSecret: string;
  redirectUri: string;
}

export function getOidcSettings(): OidcSettings | null {
  if (process.env.SSO_ENABLED !== "true") return null;
  const issuer = process.env.SSO_ISSUER;
  const clientId = process.env.SSO_CLIENT_ID;
  const clientSecret = process.env.SSO_CLIENT_SECRET;
  const redirectUri = process.env.SSO_REDIRECT_URI;
  if (!issuer || !clientId || !clientSecret || !redirectUri) {
    throw new Error(
      "SSO_ENABLED=true requires SSO_ISSUER, SSO_CLIENT_ID, SSO_CLIENT_SECRET, and SSO_REDIRECT_URI " +
        "(SPECS.md §30 org policy: sso.provider / sso.issuer / sso.client_id)."
    );
  }
  return { issuer, clientId, clientSecret, redirectUri };
}

let configCache: { issuer: string; config: client.Configuration } | null = null;

export async function getOidcClientConfig(settings: OidcSettings): Promise<client.Configuration> {
  if (configCache && configCache.issuer === settings.issuer) return configCache.config;

  // openid-client refuses plain-HTTP issuers by default (correct for
  // production). SSO_ALLOW_INSECURE_HTTP is an explicit, separate opt-in for
  // local dev/testing against a non-TLS IdP — never inferred from NODE_ENV,
  // so a misconfigured "dev" deployment can't accidentally weaken a real one.
  const allowInsecure = process.env.SSO_ALLOW_INSECURE_HTTP === "true";
  const config = await client.discovery(
    new URL(settings.issuer),
    settings.clientId,
    settings.clientSecret,
    undefined,
    allowInsecure ? { execute: [client.allowInsecureRequests] } : undefined
  );
  configCache = { issuer: settings.issuer, config };
  return config;
}

export async function buildAuthorizationUrl(settings: OidcSettings): Promise<{ url: string; state: string; codeVerifier: string }> {
  const config = await getOidcClientConfig(settings);
  const state = client.randomState();
  const codeVerifier = client.randomPKCECodeVerifier();
  const codeChallenge = await client.calculatePKCECodeChallenge(codeVerifier);

  const url = client.buildAuthorizationUrl(config, {
    redirect_uri: settings.redirectUri,
    scope: "openid email profile",
    state,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
  });

  return { url: url.href, state, codeVerifier };
}

export type OidcIdentity = SessionIdentity;

export async function handleCallback(
  settings: OidcSettings,
  callbackUrl: URL,
  expectedState: string,
  codeVerifier: string
): Promise<OidcIdentity> {
  const config = await getOidcClientConfig(settings);
  const tokens = await client.authorizationCodeGrant(config, callbackUrl, {
    expectedState,
    pkceCodeVerifier: codeVerifier,
  });
  const claims = tokens.claims();
  if (!claims?.sub) {
    throw new Error("OIDC provider did not return a subject (sub) claim in the ID token.");
  }
  return {
    sub: claims.sub,
    email: typeof claims.email === "string" ? claims.email : undefined,
    name: typeof claims.name === "string" ? claims.name : undefined,
  };
}

// Session cookie (signed, not encrypted — contains no secrets, only identity
// claims that are fine to be readable, just not forgeable) now lives in
// ./sessionToken — re-exported above for this module's existing callers.
