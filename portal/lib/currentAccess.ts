// portal/lib/currentAccess.ts — the access of the CURRENT request.
//
// Deliberately separate from lib/authz.ts. authz holds the pure decision logic
// — roles, scopes, who may see which tenant — and is imported by test/authz.test.ts,
// which runs under a bare `node --experimental-strip-types` with no Next
// runtime. Putting this `next/headers` import in authz.ts broke that suite
// immediately, which is the argument for the split rather than a workaround:
// request binding is a different concern from access rules, and only one of
// them needs a framework.
//
// Thirteen files previously repeated the two lines this replaces, and each had
// to import ROLE_HEADER and TENANT_SCOPE_HEADER purely to hand them straight
// back. Those names are an internal detail of the middleware contract.

import { headers } from "next/headers";

import { ROLE_HEADER, TENANT_SCOPE_HEADER, getAccessFromHeaderValues, type Access } from "@/lib/authz";

/**
 * Server-side only, and only behind middleware.ts: these headers are trusted
 * precisely because middleware sets them after authenticating. Never call this
 * from client code, and never let a client-supplied header reach it.
 */
export function currentAccess(): Access {
  const h = headers();
  return getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));
}
