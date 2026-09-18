// portal/lib/authz.ts — who may do what, on which app (.agent-rfc/designs/portal-phase1.md, S2).
//
// A user holds GRANTS: a role and the apps it covers. Every check asks for a
// PERMISSION, never a role — `can(access, "ops.dlq", app)` — so a role's reach
// is decided here, in one table, and nowhere else. One person may hold several
// grants: on a small project, every development role.
//
// middleware.ts resolves the authenticated identity (basic-auth user or SSO
// session) into grants and forwards them as ONE trusted request header
// (x-af-grants). The header is only meaningful because middleware.ts strips any
// client-supplied copy before setting its own; route handlers and pages must
// never read it from anywhere except currentAccess().
//
// One catalog, types derived from it, one guard — the shape lib/isolation.ts
// uses.
import { constantTimeEquals } from "./constantTime";

export const PERMISSIONS = [
  "dev.read", // the Dev workspace, for an app
  "dev.approve", // approve a design deviation (phase 2)
  "dev.allowlist", // approve an exemption from a mechanical pillar check (phase 2)
  "ops.read", // the Ops workspace, for an app
  "ops.dlq", // replay or discard a dead-letter entry
  "ops.widget", // mint a widget token
  "ops.app_settings", // edit an app's operational settings (POST /api/tenants)
  "ops.hitl", // decide a HITL gate (phase 3)
  "ops.release", // approve a production promotion (phase 4)
  "admin.apps", // register apps, issue ingest tokens, revoke widget tokens
  "admin.audit", // read the audit log
  "admin.users", // manage users (phase 2)
  "admin.org", // organisation settings, Administrators, passkey recovery (phase 2)
] as const;
export type Permission = (typeof PERMISSIONS)[number];

// The seven roles the specification names. `viewer` is not one of them: it is
// the pre-phase-1 read-only role, kept so an existing configuration grants
// exactly what it granted before (the compatibility obligation within a major
// version). It is accepted from the old `role` field only — never offered, and
// never valid in `grants`.
export const ROLES = [
  "developer",
  "design_approver",
  "operator",
  "hitl_reviewer",
  "release_approver",
  "administrator",
  "super_user",
] as const;
export type Role = (typeof ROLES)[number];
export const LEGACY_ROLES = ["viewer"] as const;
export type AnyRole = Role | (typeof LEGACY_ROLES)[number];

const ADMINISTRATOR: readonly Permission[] = PERMISSIONS.filter((p) => p !== "admin.org");

export const ROLE_PERMISSIONS: Readonly<Record<AnyRole, readonly Permission[]>> = {
  developer: ["dev.read", "dev.approve"],
  design_approver: ["dev.read", "dev.approve", "dev.allowlist"],
  // Exactly what the pre-phase-1 `operator` could do, so an old config maps onto it unchanged.
  operator: ["ops.read", "ops.dlq", "ops.widget", "ops.app_settings"],
  hitl_reviewer: ["ops.hitl"],
  release_approver: ["ops.read", "ops.release"],
  administrator: ADMINISTRATOR,
  super_user: PERMISSIONS,
  viewer: ["ops.read"],
};

/** Roles that act for the whole organisation. A new-form grant of one must cover every app. */
const ORG_WIDE: readonly AnyRole[] = ["administrator", "super_user"];

export interface Grant {
  role: AnyRole;
  // "*" = every app. Otherwise an explicit allow-list of app ids.
  apps: "*" | string[];
}

export interface Access {
  grants: Grant[];
  /** Who is signed in — the basic-auth username or the SSO email. What an audit
   *  entry names as the actor. Null when the request carries none. */
  actor: string | null;
}

export const GRANTS_HEADER = "x-af-grants";
export const ACTOR_HEADER = "x-af-actor";
/** Pre-phase-1 header names. Never set any more; still stripped from every
 *  request, so a client cannot supply one that some forgotten reader trusts. */
export const RETIRED_HEADERS = ["x-af-role", "x-af-tenant-scope"] as const;

function isAnyRole(value: unknown): value is AnyRole {
  // Own properties only: `in` also answers true for "constructor", "toString"
  // and the rest of Object.prototype, and a forged header naming one would
  // pass as a role and then crash the first permission lookup.
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(ROLE_PERMISSIONS, value);
}

function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

function isApps(value: unknown): value is "*" | string[] {
  return value === "*" || (Array.isArray(value) && value.every((v) => typeof v === "string"));
}

// ── the checks ───────────────────────────────────────────────────────────────

/**
 * Whether this access holds `permission` — for `app` when given, otherwise for
 * at least one app. The app-less form answers "may this user do this kind of
 * thing at all" (a 403); the per-app form answers "on this app" (a 404, so an
 * app outside the user's grants is indistinguishable from one that does not
 * exist). Organisation-level permissions (`admin.audit`, `admin.users`,
 * `admin.org`) are asked app-less.
 */
export function can(access: Access, permission: Permission, app?: string): boolean {
  return roleFor(access, permission, app) !== undefined;
}

/**
 * The role under which `permission` is held on `app` — what a span or an audit
 * entry records as the actor's role. With several grants a user holds several
 * roles; the one that authorised THIS action is the true answer.
 */
export function roleFor(access: Access, permission: Permission, app?: string): AnyRole | undefined {
  return access.grants.find(
    (g) =>
      ROLE_PERMISSIONS[g.role].includes(permission) &&
      (app === undefined || g.apps === "*" || g.apps.includes(app)),
  )?.role;
}

/** The apps among `candidates` on which this access holds `permission`. */
export function appsWith(access: Access, permission: Permission, candidates: string[]): string[] {
  return candidates.filter((app) => can(access, permission, app));
}

export const AREAS = ["dev", "ops", "admin"] as const;
export type Area = (typeof AREAS)[number];

/** The areas of the portal this access may enter, in the order the switcher shows them. */
export function areas(access: Access): Area[] {
  const has = (prefix: string) =>
    access.grants.some((g) => ROLE_PERMISSIONS[g.role].some((p) => p.startsWith(prefix)));
  return AREAS.filter((area) => has(`${area}.`));
}

// ── configuration ────────────────────────────────────────────────────────────

let warnedLegacy = false;
function warnLegacy(): void {
  if (warnedLegacy) return;
  warnedLegacy = true;
  console.warn(
    "Ops Portal: a user entry uses the pre-phase-1 `role` + `tenants` form. It still grants what it " +
      'always did; the new form is `grants: [{"role": "operator", "apps": ["acme"]}]` with roles ' +
      `${ROLES.join(", ")}.`,
  );
}

/**
 * One configured user's grants. The new form is `grants: [{role, apps}]`; the
 * old form is `role` + `tenants`, mapped to exactly what it granted before:
 * `viewer` → the legacy read-only role, `operator` → Operator, `admin` →
 * Administrator — each over the tenants it listed.
 */
export function parseGrants(entry: Record<string, unknown>): Grant[] {
  if (entry.grants !== undefined) {
    if (!Array.isArray(entry.grants)) throw new Error(`"grants" must be an array of {role, apps}`);
    return entry.grants.map((g: Record<string, unknown>) => {
      if (!isRole(g?.role)) {
        throw new Error(`invalid role "${String(g?.role)}" — must be one of ${ROLES.join(", ")}`);
      }
      if (!isApps(g.apps)) throw new Error(`invalid "apps" for ${g.role} — must be "*" or an array of app ids`);
      if (ORG_WIDE.includes(g.role) && g.apps !== "*") {
        throw new Error(`${g.role} acts for the whole organisation — its "apps" must be "*"`);
      }
      return { role: g.role, apps: g.apps };
    });
  }
  const legacy = { viewer: "viewer", operator: "operator", admin: "administrator" } as const;
  const role = entry.role;
  if (typeof role !== "string" || !(role in legacy)) {
    throw new Error(`invalid role "${String(role)}" — use "grants" with roles ${ROLES.join(", ")}`);
  }
  if (!isApps(entry.tenants)) {
    throw new Error(`invalid "tenants" field — must be "*" or an array of tenant id strings`);
  }
  warnLegacy();
  return [{ role: legacy[role as keyof typeof legacy], apps: entry.tenants }];
}

interface BasicAuthUserRecord {
  username: string;
  password: string;
  grants: Grant[];
}

interface SsoUserRecord {
  email: string;
  grants: Grant[];
}

// OPS_PORTAL_USERS: JSON array of {username, password, grants} (or the old
// {role, tenants}). Falls back to the single OPS_PORTAL_USER/OPS_PORTAL_PASSWORD
// pair, which is Administrator on every app — as it always was.
function getBasicAuthUsers(): BasicAuthUserRecord[] {
  const raw = process.env.OPS_PORTAL_USERS;
  if (raw) {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error("OPS_PORTAL_USERS must be a JSON array");
    return parsed.map((u) => ({
      username: String(u.username),
      password: String(u.password),
      grants: parseGrants(u),
    }));
  }
  const user = process.env.OPS_PORTAL_USER;
  const pass = process.env.OPS_PORTAL_PASSWORD;
  if (!user || !pass) return [];
  return [{ username: user, password: pass, grants: SINGLE_USER_GRANTS }];
}

/** What the single-user OPS_PORTAL_USER/OPS_PORTAL_PASSWORD configuration grants. */
export const SINGLE_USER_GRANTS: Grant[] = [{ role: "administrator", apps: "*" }];

// OPS_PORTAL_SSO_USERS: JSON array of {email, grants} (or the old {role,
// tenants}), keyed by the IdP's email claim. An authenticated-but-unlisted SSO
// identity gets no grants at all rather than being rejected outright — see
// getAccessForSsoEmail().
function getSsoUsers(): SsoUserRecord[] {
  const raw = process.env.OPS_PORTAL_SSO_USERS;
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) throw new Error("OPS_PORTAL_SSO_USERS must be a JSON array");
  return parsed.map((u) => ({ email: String(u.email).toLowerCase(), grants: parseGrants(u) }));
}

export function verifyBasicAuthCredentials(username: string, password: string): Access | null {
  const record = getBasicAuthUsers().find((u) => u.username === username);
  // Constant-time: this is a user password, and `!==` short-circuits on the
  // first differing byte. Compare unconditionally even when the username is
  // unknown, so a missing user and a wrong password take the same path — a
  // fast "no such user" is a username oracle.
  const expected = record?.password ?? "";
  const ok = constantTimeEquals(expected, password);
  if (!record || !ok) return null;
  return { grants: record.grants, actor: username };
}

export function getAccessForSsoEmail(email: string | undefined): Access {
  if (!email) return { grants: [], actor: null };
  const record = getSsoUsers().find((u) => u.email === email.toLowerCase());
  return { grants: record ? record.grants : [], actor: email.toLowerCase() };
}

// ── the trusted header ───────────────────────────────────────────────────────

export function encodeGrantsHeader(grants: Grant[]): string {
  // URI-encoded JSON: app ids are not constrained to a charset a hand-rolled
  // separator format could survive.
  return encodeURIComponent(JSON.stringify(grants));
}

/**
 * The grants middleware set. Deny by default: a missing or unreadable header is
 * no grants, and a grant naming an unknown role or malformed apps is dropped —
 * never widened to something that parses.
 */
export function decodeGrantsHeader(value: string | null): Grant[] {
  if (!value) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(decodeURIComponent(value));
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];
  return parsed.filter(
    (g): g is Grant => typeof g === "object" && g !== null && isAnyRole(g.role) && isApps(g.apps),
  );
}

/**
 * A copy of `headers` with every access header removed — the current one and
 * the retired names. Middleware calls this before setting its own, so no
 * client-supplied copy can reach a handler, and a client cannot supply a
 * retired name that some forgotten reader still trusts.
 */
export function stripAccessHeaders(headers: Headers): Headers {
  const stripped = new Headers(headers);
  stripped.delete(GRANTS_HEADER);
  stripped.delete(ACTOR_HEADER);
  for (const name of RETIRED_HEADERS) stripped.delete(name);
  return stripped;
}

// Reads the trusted header middleware attaches to every request after
// successful authentication. Only call this from server-side route handlers
// and pages running behind middleware.ts — never expose the header name to
// client code.
export function getAccessFromHeaderValue(grantsHeader: string | null, actorHeader: string | null = null): Access {
  return { grants: decodeGrantsHeader(grantsHeader), actor: decodeActorHeader(actorHeader) };
}

export function encodeActorHeader(actor: string | null): string {
  return encodeURIComponent(actor ?? "");
}

export function decodeActorHeader(value: string | null): string | null {
  if (!value) return null;
  try {
    return decodeURIComponent(value) || null;
  } catch {
    return null;
  }
}
