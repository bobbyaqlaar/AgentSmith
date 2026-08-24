// portal/test/safeUrl.test.ts — the two URL guards, and the inputs that got
// past their predecessors.
//
// Both replaced a check that read as if it handled the case: `startsWith("/")`
// for a redirect destination, and nothing at all for a stored URL the portal
// later fetches and renders as a link. Every case below is one that the old
// code accepted.

import assert from "node:assert/strict";

import { isSafeHttpUrl, safeRedirectPath } from "../lib/safeUrl.ts";

const ORIGIN = "https://ops.example.com";

let passed = 0;
function test(name: string, fn: () => void) {
  try {
    fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

test("a protocol-relative destination is refused", () => {
  // `//evil.example`.startsWith("/") is true, and `new URL` resolves it to a
  // different origin — so the old guard sent users off-site immediately after
  // a successful SSO login, the moment they are least suspicious.
  assert.equal(safeRedirectPath("//evil.example", ORIGIN), null);
  assert.equal(safeRedirectPath("//evil.example/path", ORIGIN), null);
});

test("a backslash-prefixed destination is refused", () => {
  // Browsers normalise `\` to `/` in this position, and so does `new URL`.
  assert.equal(safeRedirectPath("/\\evil.example", ORIGIN), null);
  assert.equal(safeRedirectPath("/\\\\evil.example", ORIGIN), null);
});

test("an absolute URL is refused even when it names this origin", () => {
  // Nothing needs it, and accepting absolute URLs means the next reader has to
  // re-derive why one host string is safe.
  assert.equal(safeRedirectPath(`${ORIGIN}/dlq`, ORIGIN), null);
  assert.equal(safeRedirectPath("https://evil.example/dlq", ORIGIN), null);
  assert.equal(safeRedirectPath("javascript:alert(1)", ORIGIN), null);
});

test("an ordinary in-app path survives, query and fragment included", () => {
  // A guard that rejects working destinations gets deleted, so this is as
  // important as the refusals above.
  assert.equal(safeRedirectPath("/dlq", ORIGIN), "/dlq");
  assert.equal(safeRedirectPath("/tenants/acme?tab=cost", ORIGIN), "/tenants/acme?tab=cost");
  assert.equal(safeRedirectPath("/audit#latest", ORIGIN), "/audit#latest");
  assert.equal(safeRedirectPath("/", ORIGIN), "/");
});

test("nothing at all is not a destination", () => {
  assert.equal(safeRedirectPath(null, ORIGIN), null);
  assert.equal(safeRedirectPath(undefined, ORIGIN), null);
  assert.equal(safeRedirectPath("", ORIGIN), null);
  assert.equal(safeRedirectPath("dlq", ORIGIN), null); // relative, no leading slash
});

test("only http(s) is storable and fetchable", () => {
  assert.equal(isSafeHttpUrl("https://phoenix.example.com"), true);
  assert.equal(isSafeHttpUrl("http://localhost:6006"), true);
  // The product's own defaults are internal hosts — see lib/safeUrl on why the
  // check is the scheme and deliberately not the host.
  assert.equal(isSafeHttpUrl("http://phoenix:6006"), true);
});

test("a scheme that is not http(s) is refused", () => {
  // `javascript:` reached an <a href> on the tenant page; the rest reached
  // fetch(), four call sites deep.
  assert.equal(isSafeHttpUrl("javascript:alert(1)"), false);
  assert.equal(isSafeHttpUrl("file:///etc/passwd"), false);
  assert.equal(isSafeHttpUrl("data:text/html,<script>"), false);
  assert.equal(isSafeHttpUrl("gopher://example.com"), false);
});

test("a non-URL is refused rather than throwing", () => {
  assert.equal(isSafeHttpUrl("not a url"), false);
  assert.equal(isSafeHttpUrl(""), false);
  assert.equal(isSafeHttpUrl("   "), false);
  assert.equal(isSafeHttpUrl(null), false);
  assert.equal(isSafeHttpUrl(undefined), false);
  assert.equal(isSafeHttpUrl(42), false);
  assert.equal(isSafeHttpUrl({ href: "https://example.com" }), false);
});

console.log(`\n${passed} passed`);
