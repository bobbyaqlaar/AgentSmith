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

// WEB-STANDARD APIS ONLY. This file was written with node:crypto's
// timingSafeEqual and Buffer, and that broke `next build` outright:
//
//   Module build failed: UnhandledSchemeError: Reading from "node:crypto"
//   is not handled by plugins (Unhandled scheme).
//
// middleware.ts runs on the EDGE runtime and imports lib/authz, which imports
// this module — so a Node-only builtin here is not a lint preference, it is a
// production build failure. `authz.ts` had no crypto import until the password
// comparison was made constant-time; the security fix and the Edge constraint
// arrived in the same commit and the second went unnoticed, because `tsc
// --noEmit` and `npm test` both pass on this file. Only `next build` sees it.
//
// TextEncoder is available in the Edge runtime, in Node, and under the bare
// type-stripping test runner. Buffer is available in none of the first.

/**
 * `!==` on a secret leaks its length and, in principle, its prefix through
 * response timing. The window is small over HTTP and rarely the easiest way in,
 * but a correct comparison costs one function and removes the question.
 *
 * The loop is unconditional and accumulates with `|=`: every byte of an
 * equal-length pair is read whatever the first byte said, so the time taken
 * does not depend on WHERE the inputs diverge. The length check before it is
 * variable-time and unavoidably leaks length — timingSafeEqual throws on a
 * length mismatch, so it has the same property. It is the content that matters.
 */
export function constantTimeEquals(a: string, b: string): boolean {
  const encoder = new TextEncoder();
  const bytesA = encoder.encode(a);
  const bytesB = encoder.encode(b);
  if (bytesA.length !== bytesB.length) return false;

  let diff = 0;
  for (let i = 0; i < bytesA.length; i++) {
    diff |= bytesA[i] ^ bytesB[i];
  }
  return diff === 0;
}
