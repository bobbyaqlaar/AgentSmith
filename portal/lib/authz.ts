// portal/lib/authz.ts — role-based tenant access control (SPECS.md §26:
// "Role-based access in the portal (viewer, operator, admin) controls which
// tenants each user can view.").
//
// middleware.ts resolves the authenticated identity (basic-auth user or SSO
// session) into a role + tenant scope and forwards them downstream as
// trusted request headers (x-af-role / x-af-tenant-scope) — these headers
// are only meaningful because middleware.ts strips any client-supplied copy
// before setting its own; route handlers and pages must never read them from
// anywhere except getAccess() below.

export type Role = "viewer" | "operator" | "admin";

export interface Access {
  role: Role;
  // "*" = all tenants. Otherwise an explicit allow-list of tenant ids.
  tenantScope: "*" | string[];
}

export const ROLE_HEADER = "x-af-role";
export const TENANT_SCOPE_HEADER = "x-af-tenant-scope";

interface UserRecord {
  role: Role;
  tenants: "*" | string[];
}

interface BasicAuthUserRecord extends UserRecord {
  username: string;
  password: string;
}

interface SsoUserRecord extends UserRecord {
  email: string;
}

function parseRole(value: unknown): Role {
  if (value === "viewer" || value === "operator" || value === "admin") return value;
  throw new Error(`invalid role "${String(value)}" — must be viewer, operator, or admin`);
}

function parseTenants(value: unknown): "*" | string[] {
  if (value === "*") return "*";
  if (Array.isArray(value) && value.every((v) => typeof v === "string")) return value;
  throw new Error(`invalid "tenants" field — must be "*" or an array of tenant id strings`);
}

// OPS_PORTAL_USERS: JSON array of {username, password, role, tenants}.
// Falls back to the single legacy OPS_PORTAL_USER/OPS_PORTAL_PASSWORD pair
// (granted "admin" + "*" for backward compatibility with pre-RBAC configs).
export function getBasicAuthUsers(): BasicAuthUserRecord[] {
  const raw = process.env.OPS_PORTAL_USERS;
  if (raw) {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error("OPS_PORTAL_USERS must be a JSON array");
    return parsed.map((u) => ({
      username: String(u.username),
      password: String(u.password),
      role: parseRole(u.role),
      tenants: parseTenants(u.tenants),
    }));
  }
  const user = process.env.OPS_PORTAL_USER;
  const pass = process.env.OPS_PORTAL_PASSWORD;
  if (!user || !pass) return [];
  return [{ username: user, password: pass, role: "admin", tenants: "*" }];
}

// OPS_PORTAL_SSO_USERS: JSON array of {email, role, tenants}, keyed by the
// email claim returned by the IdP. An authenticated-but-unlisted SSO identity
// gets the most restrictive possible access (viewer, empty scope) rather
// than being rejected outright — see getAccessForSsoEmail().
export function getSsoUsers(): SsoUserRecord[] {
  const raw = process.env.OPS_PORTAL_SSO_USERS;
  if (!raw) return [];
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed)) throw new Error("OPS_PORTAL_SSO_USERS must be a JSON array");
  return parsed.map((u) => ({
    email: String(u.email).toLowerCase(),
    role: parseRole(u.role),
    tenants: parseTenants(u.tenants),
  }));
}

export function getAccessForBasicAuthUser(username: string): Access | null {
  const record = getBasicAuthUsers().find((u) => u.username === username);
  if (!record) return null;
  return { role: record.role, tenantScope: record.tenants };
}

export function verifyBasicAuthCredentials(username: string, password: string): Access | null {
  const record = getBasicAuthUsers().find((u) => u.username === username);
  if (!record || record.password !== password) return null;
  return { role: record.role, tenantScope: record.tenants };
}

export function getAccessForSsoEmail(email: string | undefined): Access {
  if (!email) return { role: "viewer", tenantScope: [] };
  const record = getSsoUsers().find((u) => u.email === email.toLowerCase());
  if (!record) return { role: "viewer", tenantScope: [] };
  return { role: record.role, tenantScope: record.tenants };
}

export function encodeTenantScopeHeader(scope: "*" | string[]): string {
  return scope === "*" ? "*" : scope.join(",");
}

export function decodeTenantScopeHeader(value: string | null): "*" | string[] {
  if (!value) return [];
  if (value === "*") return "*";
  return value.split(",").filter(Boolean);
}

export function canAccessTenant(access: Access, tenantId: string): boolean {
  return access.tenantScope === "*" || access.tenantScope.includes(tenantId);
}

export function filterTenantIds(access: Access, tenantIds: string[]): string[] {
  return access.tenantScope === "*" ? tenantIds : tenantIds.filter((id) => access.tenantScope.includes(id));
}

export function canWrite(access: Access): boolean {
  return access.role === "operator" || access.role === "admin";
}

export function canAdmin(access: Access): boolean {
  return access.role === "admin";
}

// Reads the trusted headers middleware.ts attaches to every request after
// successful authentication. Only call this from server-side route handlers
// and pages running behind middleware.ts — never expose these header names
// to client code.
export function getAccessFromHeaderValues(roleHeader: string | null, scopeHeader: string | null): Access {
  const role = roleHeader === "viewer" || roleHeader === "operator" || roleHeader === "admin" ? roleHeader : "viewer";
  return { role, tenantScope: decodeTenantScopeHeader(scopeHeader) };
}
