// portal/middleware.ts — dashboard auth gate.
//
// Default: HTTP basic auth (SPECS.md §15: "team deployment: basic auth
// minimum"). Set OPS_PORTAL_USER / OPS_PORTAL_PASSWORD. If unset, the portal
// refuses to serve requests rather than running unauthenticated.
//
// SSO_ENABLED=true (enterprise pack, §30: "Ops Portal requires SSO login"):
// basic auth is REPLACED (not augmented) by an OIDC session cookie — see
// lib/oidc.ts and app/api/auth/*. Unauthenticated browser requests for an
// HTML page are redirected to /api/auth/login; API requests get a plain 401.

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  ROLE_HEADER,
  TENANT_SCOPE_HEADER,
  encodeTenantScopeHeader,
  getAccessForSsoEmail,
  verifyBasicAuthCredentials,
} from "./lib/authz";
import { SESSION_COOKIE_NAME, verifySessionToken } from "./lib/sessionToken";
import {
  checkSessionRevocation,
  resolveRevocationMode,
} from "./lib/ssoRevocationMode";

// /api/sync/* is machine-to-machine (tenant CD workflows) and authenticates
// with its own bearer token (OPS_PORTAL_SYNC_TOKEN) inside the route handler
// instead — CI runners shouldn't need the human dashboard's basic-auth creds.
//
// /api/widget/* is called directly from end users' browsers, embedded in a
// tenant's own web app — it can't carry the dashboard's basic-auth creds
// either. It authenticates via its own per-tenant scoped token instead (see
// app/api/widget/status/route.ts) — that token, not basic auth, is the
// access-control boundary for this path.
//
// /api/audit/append is the CLI/CI write path for the audit log (§30) — same
// reasoning as /api/sync/*, gated by AUDIT_LOG_WRITE_TOKEN instead. Reading
// the audit log (GET /api/audit) still requires basic auth/SSO, unaffected.
//
// /api/runs/ingest is runtime/llm_gateway.py's best-effort run-status push
// (Product_Archive.md P2a) — same machine-to-machine reasoning as
// /api/sync/*, gated by OPS_PORTAL_SYNC_TOKEN inside the route handler.
//
// /api/auth/* must always be reachable unauthenticated — it IS the
// login/callback/logout flow; gating it would make login impossible.
// Each exclusion is anchored to a path-segment boundary (`(?:/|$)`) so a
// future route that merely starts with one of these literal strings — e.g.
// /api/audit/appendix, /api/widgetry, /api/syncing — is NOT accidentally
// swept into the unauthenticated set. Plain string-prefix matching here was
// a latent auth-bypass footgun (see Product_Archive.md 2.6).
export const config = {
  matcher:
    "/((?!_next/static(?:/|$)|_next/image(?:/|$)|favicon\\.ico$|api/sync(?:/|$)|api/widget(?:/|$)|api/audit/append(?:/|$)|api/runs/ingest(?:/|$)|api/auth(?:/|$)).*)",
};

// Strip any client-supplied copy of the trusted RBAC headers before they can
// reach a route handler — otherwise an unauthenticated caller could simply
// set `x-af-role: admin` itself and skip the lookup below entirely.
function stripForgedAccessHeaders(request: NextRequest): Headers {
  const headers = new Headers(request.headers);
  headers.delete(ROLE_HEADER);
  headers.delete(TENANT_SCOPE_HEADER);
  return headers;
}

function withAccessHeaders(headers: Headers, role: string, tenantScope: "*" | string[]): Headers {
  headers.set(ROLE_HEADER, role);
  headers.set(TENANT_SCOPE_HEADER, encodeTenantScopeHeader(tenantScope));
  return headers;
}

async function probeSessionStatus(
  request: NextRequest,
  jti: string
): Promise<{ ok: boolean; revoked?: boolean }> {
  const url = new URL("/api/auth/session-status", request.nextUrl.origin);
  url.searchParams.set("jti", jti);
  const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
  if (!res.ok) return { ok: false };
  const data = (await res.json()) as { revoked?: boolean };
  return { ok: true, revoked: data.revoked === true };
}

/** SSO session check. `unavailable` means session-status probe failed under fail-closed. */
async function checkSsoSession(
  request: NextRequest
): Promise<{ email?: string } | null | "unavailable"> {
  if (!process.env.SSO_SESSION_SECRET) return null; // misconfigured — fail closed, see middleware() below
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return null;
  // Delegates to lib/sessionToken.ts instead of re-verifying the JWT inline
  // with a hardcoded cookie name — previously this duplicated oidc.ts's
  // verification logic with its own copy of the secret-reading and
  // jwtVerify call (Product_Archive.md 4.2).
  const session = await verifySessionToken(token);
  if (!session) return null;
  // Server-side revocation check (Product_Archive.md 4.14 / SEC-SSO-001) —
  // see lib/sessionRevocation.ts for why this is a fetch to a Node-runtime
  // route rather than a direct DB call from this Edge-runtime middleware.
  // SSO_REVOCATION_MODE=fail-closed → 503 when session-status unreachable;
  // default remains fail-open (legacy).
  const decision = await checkSessionRevocation({
    jti: session.jti,
    mode: resolveRevocationMode(),
    fetchStatus: (jti) => probeSessionStatus(request, jti),
  });
  if (decision === "unavailable") return "unavailable";
  if (decision === "deny") return null;
  return { email: session.email };
}

function wantsHtml(request: NextRequest): boolean {
  return (request.headers.get("accept") ?? "").includes("text/html");
}

export async function middleware(request: NextRequest) {
  if (process.env.SSO_ENABLED === "true") {
    if (!process.env.SSO_SESSION_SECRET) {
      return new NextResponse(
        "Ops Portal misconfigured: SSO_ENABLED=true requires SSO_SESSION_SECRET " +
          "(plus SSO_ISSUER, SSO_CLIENT_ID, SSO_CLIENT_SECRET, SSO_REDIRECT_URI).",
        { status: 500 }
      );
    }

    const session = await checkSsoSession(request);
    if (session === "unavailable") {
      return NextResponse.json(
        {
          error:
            "session revocation check unavailable (SSO_REVOCATION_MODE=fail-closed)",
        },
        { status: 503 }
      );
    }
    if (session) {
      const access = getAccessForSsoEmail(session.email);
      const headers = withAccessHeaders(stripForgedAccessHeaders(request), access.role, access.tenantScope);
      return NextResponse.next({ request: { headers } });
    }

    if (wantsHtml(request)) {
      const loginUrl = new URL("/api/auth/login", request.url);
      loginUrl.searchParams.set("redirect_to", new URL(request.url).pathname);
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.json({ error: "authentication required (SSO)" }, { status: 401 });
  }

  // ── Default: HTTP basic auth ──────────────────────────────────────────────
  const user = process.env.OPS_PORTAL_USER;
  const pass = process.env.OPS_PORTAL_PASSWORD;
  const hasMultiUserConfig = !!process.env.OPS_PORTAL_USERS;

  if (!hasMultiUserConfig && (!user || !pass)) {
    return new NextResponse(
      "Ops Portal misconfigured: OPS_PORTAL_USER and OPS_PORTAL_PASSWORD must be set " +
        "(or OPS_PORTAL_USERS for multi-user RBAC) before the portal will serve traffic " +
        "(SPECS.md §15 — no unauthenticated team-shared deployments).",
      { status: 500 }
    );
  }

  const authHeader = request.headers.get("authorization");
  if (authHeader?.startsWith("Basic ")) {
    const decoded = Buffer.from(authHeader.slice(6), "base64").toString("utf-8");
    const sepIdx = decoded.indexOf(":");
    const reqUser = sepIdx === -1 ? decoded : decoded.slice(0, sepIdx);
    const reqPass = sepIdx === -1 ? "" : decoded.slice(sepIdx + 1);
    // Legacy single-user fallback (OPS_PORTAL_USER/PASSWORD) always grants
    // admin/"*" — same behavior as before RBAC existed. OPS_PORTAL_USERS
    // (multi-user, per-user role + tenant scope) takes precedence when set.
    if (!process.env.OPS_PORTAL_USERS) {
      if (reqUser === user && reqPass === pass) {
        const headers = withAccessHeaders(stripForgedAccessHeaders(request), "admin", "*");
        return NextResponse.next({ request: { headers } });
      }
    } else {
      const access = verifyBasicAuthCredentials(reqUser, reqPass);
      if (access) {
        const headers = withAccessHeaders(stripForgedAccessHeaders(request), access.role, access.tenantScope);
        return NextResponse.next({ request: { headers } });
      }
    }
  }

  return new NextResponse("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="AgentSmith Ops Portal"' },
  });
}
