// portal/lib/safeUrl.ts — the two URL questions this portal keeps getting
// wrong, in one place.
//
// Both are "a string that looks like a path/URL is not the same as one that
// goes where you think", and both had a guard that read as if it handled the
// case and did not.
//
// WEB-STANDARD APIS ONLY — `new URL` and nothing else. lib/authz.ts is on
// middleware's Edge import graph and may one day want the redirect helper;
// see lib/constantTime.ts's header for what a Node builtin costs there.

/**
 * A caller-supplied post-login destination, or null.
 *
 * `redirect_to.startsWith("/")` was the whole check, and it accepts
 * `//evil.example` and `/\evil.example` — protocol-relative URLs that
 * `new URL(value, origin)` resolves to a DIFFERENT ORIGIN. The login flow
 * carried that value in a cookie and the callback redirected to it, so a
 * crafted login link sent a user to an attacker's site immediately after a
 * successful SSO login, which is the moment they are least suspicious.
 *
 * Resolving and comparing origins is the check, rather than another prefix
 * rule: string rules keep missing a form (`//`, `/\`, `/%09/`, a bare
 * `https:`), and the question was always "does this leave the origin".
 */
export function safeRedirectPath(value: string | null | undefined, origin: string): string | null {
  if (!value || !value.startsWith("/")) return null;
  try {
    const resolved = new URL(value, origin);
    if (resolved.origin !== new URL(origin).origin) return null;
    // Returned as a path, never as an absolute URL: the caller resolves it
    // against its own origin, so there is no second chance to point elsewhere.
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return null;
  }
}

/**
 * True for an `http:` / `https:` URL the portal is willing to store and fetch.
 *
 * `tenants.phoenix_base_url` and `tenants.replay_webhook_url` are supplied over
 * the API and are then (a) fetched server-side — four call sites: Phoenix
 * health, Phoenix GraphQL, the shadow-eval REST read, and the DLQ replay POST —
 * and (b) rendered as an `<a href>` on the tenant page. Neither was validated,
 * so `javascript:…` reached an anchor React will happily render, and any other
 * scheme reached `fetch`.
 *
 * WHAT THIS DELIBERATELY DOES NOT DO: block private or loopback hosts. The
 * product's own defaults are `http://phoenix:6006` (docker-compose) and
 * `http://localhost:6006` (a developer machine) — an SSRF blocklist would
 * reject the intended configuration. The residual is bounded by who can write
 * these fields: an operator, only for tenants inside its own scope, which is
 * the check `POST /api/tenants` was missing.
 */
export function isSafeHttpUrl(value: unknown): value is string {
  if (typeof value !== "string" || !value.trim()) return false;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
