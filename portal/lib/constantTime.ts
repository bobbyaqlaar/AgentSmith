// portal/lib/constantTime.ts — constant-time string comparison.
//
// Its own module, with no framework imports, because both callers must be able
// to reach it: lib/bearerAuth.ts (which imports next/server) and lib/authz.ts
// (which must stay framework-free so test/authz.test.ts can run under bare
// node). Putting it in bearerAuth.ts would have dragged next/server into authz
// and broken that suite — the same mistake currentAccess() made once already.

// NB: modules in lib/ import each other RELATIVELY ("./x"), never via the "@/"
// alias. tsc resolves the alias, the bare `node --experimental-strip-types`
// runner used by `npm test` does not — an alias here fails at runtime only, in
// the test suite, with a module-not-found that looks nothing like the cause.
import { timingSafeEqual } from "node:crypto";

/**
 * `!==` on a secret leaks its length and, in principle, its prefix through
 * response timing. The window is small over HTTP and rarely the easiest way in,
 * but a correct comparison costs one function and removes the question.
 *
 * timingSafeEqual throws when lengths differ, so the length check comes first.
 * That check is itself variable-time and unavoidably leaks length; it is the
 * content that matters.
 */
export function constantTimeEquals(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  if (bufA.length !== bufB.length) return false;
  return timingSafeEqual(bufA, bufB);
}
