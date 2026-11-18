// portal/proxy.ts — dashboard auth gate.
//
// Default: HTTP basic auth (docs/DESIGN.md › Universal Observability Platform: "team deployment: basic auth
// minimum"). Set OPS_PORTAL_USER / OPS_PORTAL_PASSWORD. If unset, the portal
// refuses to serve requests rather than running unauthenticated.
//
// SSO_ENABLED=true (enterprise pack, §30: "Ops Portal requires SSO login"):
// basic auth is REPLACED (not augmented) by an OIDC session cookie — see
// lib/oidc.ts and app/api/auth/*. Unauthenticated browser requests for an
// HTML page are redirected to /api/auth/login; API requests get a plain 401.

import { NextResponse } from "next/server";
import { appendAuditEvent } from "./lib/auditLog";
import type { NextRequest } from "next/server";
import {
  ACTOR_HEADER,
  GRANTS_HEADER,
  encodeActorHeader,
  encodeGrantsHeader,
  getAccessForSsoEmail,
  stripAccessHeaders,
  type Grant,
} from "./lib/authz";
import { SESSION_COOKIE_NAME, refreshedSessionToken, secureCookies, sessionLimits, verifySessionToken, type VerifiedSession } from "./lib/sessionToken";
import { basicSignIn } from "./lib/signInPolicy";
import {
  checkSessionRevocation,
  interpretStatusResponse,
  resolveRevocationMode,
  type ProbeResult,
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
// /api/runs/ingest is agentsmith/llm_gateway.py's best-effort run-status push
// (docs/PRODUCT_ARCHIVE.md P2a) — same machine-to-machine reasoning as
// /api/sync/*, gated by OPS_PORTAL_SYNC_TOKEN inside the route handler.
//
// /api/dev/ingest is an app's CI sending the process gate's record (portal
// phase 1) — authenticated inside the handler by that app's own ingest token.
//
// /api/ops/ingest is an app's running workers reporting by the Ops contract
// (contract/ops/v1) — authenticated inside the handler by that app's own Ops
// token, which alone decides the app.
//
// /api/compliance/sync is an app's CD exchanging compliance attestations
// (contract/compliance/v1) — authenticated inside the handler by that app's own
// Ops token, which alone decides the app.
//
// /api/dev/scaffold/* is `agentsmith tenant init --from <id>` pulling an intake
// and marking it consumed — authenticated inside the handler by that intake's
// own single-use token. Creating an intake (/api/dev/intakes) is NOT excluded:
// a person does that, signed in.
//
// /api/auth/* must always be reachable unauthenticated — it IS the
// login/callback/logout flow; gating it would make login impossible.
// Each exclusion is anchored to a path-segment boundary (`(?:/|$)`) so a
// future route that merely starts with one of these literal strings — e.g.
// /api/audit/appendix, /api/widgetry, /api/syncing — is NOT accidentally
// swept into the unauthenticated set. Plain string-prefix matching here was
// a latent auth-bypass footgun (see docs/PRODUCT_ARCHIVE.md 2.6).
export const config = {
  matcher:
    "/((?!_next/static(?:/|$)|_next/image(?:/|$)|favicon\\.ico$|api/sync(?:/|$)|api/widget(?:/|$)|api/audit/append(?:/|$)|api/runs/ingest(?:/|$)|api/dev/ingest(?:/|$)|api/ops/ingest(?:/|$)|api/compliance/sync(?:/|$)|api/dev/scaffold(?:/|$)|api/auth(?:/|$)).*)",
};

// Strip any client-supplied copy of the trusted access header before it can
// reach a route handler — otherwise an unauthenticated caller could simply
// set it itself and skip the lookup below entirely (lib/authz.stripAccessHeaders).
function stripForgedAccessHeaders(request: NextRequest): Headers {
  return stripAccessHeaders(request.headers);
}

function withAccessHeaders(headers: Headers, grants: Grant[], actor: string | null): Headers {
  headers.set(GRANTS_HEADER, encodeGrantsHeader(grants));
  headers.set(ACTOR_HEADER, encodeActorHeader(actor));
  return headers;
}

async function probeSessionStatus(
  request: NextRequest,
  jti: string
): Promise<ProbeResult> {
  const url = new URL("/api/auth/session-status", request.nextUrl.origin);
  url.searchParams.set("jti", jti);
  const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
  // The response is READ by interpretStatusResponse rather than here, so the
  // rule for "what counts as an answer" has one home and the tests exercise
  // the same one middleware runs. This function used to decide it inline with
  // `data.revoked === true`, which turns any body without a verdict — the
  // shape the route returned on a database error — into "not revoked".
  const body = await res.json().catch(() => null);
  return interpretStatusResponse(res.status, body);
}

/** SSO session check. `unavailable` means session-status probe failed under fail-closed. */
async function checkSsoSession(
  request: NextRequest
): Promise<{ email?: string; session: VerifiedSession } | null | "unavailable"> {
  if (!process.env.SSO_SESSION_SECRET) return null; // misconfigured — fail closed, see middleware() below
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return null;
  // Delegates to lib/sessionToken.ts instead of re-verifying the JWT inline
  // with a hardcoded cookie name — previously this duplicated oidc.ts's
  // verification logic with its own copy of the secret-reading and
  // jwtVerify call (docs/PRODUCT_ARCHIVE.md 4.2).
  const session = await verifySessionToken(token);
  if (!session) return null;
  // Server-side revocation check (docs/PRODUCT_ARCHIVE.md 4.14 / SEC-SSO-001) —
  // see lib/sessionRevocation.ts for why this is a fetch to a Node-runtime
  // route rather than a direct DB call from here.
  // SSO_REVOCATION_MODE=fail-closed → 503 when session-status unreachable;
  // default remains fail-open (legacy).
  const decision = await checkSessionRevocation({
    jti: session.jti,
    mode: resolveRevocationMode(),
    fetchStatus: (jti) => probeSessionStatus(request, jti),
  });
  if (decision === "unavailable") return "unavailable";
  if (decision === "deny") return null;
  return { email: session.email, session };
}

function wantsHtml(request: NextRequest): boolean {
  return (request.headers.get("accept") ?? "").includes("text/html");
}

export async function proxy(request: NextRequest) {
  // A browser sends Basic credentials on a cross-site POST by itself. No page of
  // this portal makes one, and machine routes never reach this function.
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method) && request.headers.get("sec-fetch-site") === "cross-site") {
    return NextResponse.json({ error: "cross-site requests are refused" }, { status: 403 });
  }
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
      const headers = withAccessHeaders(stripForgedAccessHeaders(request), access.grants, access.actor);
      const response = NextResponse.next({ request: { headers } });
      // Activity extends the idle window, never the absolute limit.
      const refreshed = await refreshedSessionToken(session.session);
      if (refreshed) {
        response.cookies.set(SESSION_COOKIE_NAME, refreshed, { httpOnly: true, secure: secureCookies(), sameSite: "lax", maxAge: sessionLimits().absoluteSeconds, path: "/" });
      }
      return response;
    }

    if (wantsHtml(request)) {
      const loginUrl = new URL("/api/auth/login", request.url);
      loginUrl.searchParams.set("redirect_to", new URL(request.url).pathname);
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.json({ error: "authentication required (SSO)" }, { status: 401 });
  }

  // A compliance profile refuses shared-password sign-in outright: it cannot be
  // tied to multi-factor, a session or a named person.
  if (process.env.COMPLIANCE_PROFILE) {
    return new NextResponse("Ops Portal misconfigured: a compliance profile requires SSO_ENABLED=true; HTTP Basic is refused.", { status: 500 });
  }

  // ── Default: HTTP basic auth ──────────────────────────────────────────────
  const user = process.env.OPS_PORTAL_USER;
  const pass = process.env.OPS_PORTAL_PASSWORD;
  const hasMultiUserConfig = !!process.env.OPS_PORTAL_USERS;

  if (!hasMultiUserConfig && (!user || !pass)) {
    return new NextResponse(
      "Ops Portal misconfigured: OPS_PORTAL_USER and OPS_PORTAL_PASSWORD must be set " +
        "(or OPS_PORTAL_USERS for multi-user RBAC) before the portal will serve traffic " +
        "(docs/DESIGN.md › Universal Observability Platform — no unauthenticated team-shared deployments).",
      { status: 500 }
    );
  }

  // Only names that have an account are counted, and a locked account is answered as a
  // wrong password is: a flood of invented names can neither fill the lockout nor refuse
  // real users, and the answer does not say which names exist (P3-R6). lib/signInPolicy
  // decides; this only answers.
  const signIn = basicSignIn(request.headers.get("authorization"));
  if (signIn?.granted) {
    const headers = withAccessHeaders(stripForgedAccessHeaders(request), signIn.granted.grants, signIn.granted.actor);
    return NextResponse.next({ request: { headers } });
  }
  // Once per lockout: every failure would let anyone fill the audit log.
  if (signIn?.lockedNow) {
    await appendAuditEvent({ eventType: "session_denied", actorId: signIn.user, tenantId: null, details: { reason: "locked out after repeated failed sign-ins" } })
      .catch(() => undefined); // the refusal stands whether or not it could be logged
  }

  return new NextResponse("Authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="AgentSmith Ops Portal"' },
  });
}
