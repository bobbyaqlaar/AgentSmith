// portal/test/apps.test.ts — what Administration › Apps accepts (portal phase 1, S6).
// Pure: the same validator the routes run, without a database.
//
// Run (from portal/):
//   node --experimental-strip-types \
//     --experimental-loader=./test/ts-extension-loader.mjs \
//     test/apps.test.ts

import assert from "node:assert/strict";

import { parseAppInput } from "../lib/apps.ts";

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

const good = {
  id: "kyc-sentinel",
  name: "KYC Sentinel",
  repoUrl: "https://github.com/bobbyaqlaar/KycSentinel",
  repoProvider: "github",
  defaultBranch: "main",
};

function refused(body: unknown, mode: "create" | "update", why: RegExp) {
  const result = parseAppInput(body, mode);
  assert.equal(result.ok, false, "expected a refusal");
  if (!result.ok) assert.match(result.error, why);
}

test("a complete app is accepted, trimmed", () => {
  const result = parseAppInput({ ...good, name: "  KYC Sentinel  " }, "create");
  assert.ok(result.ok);
  if (result.ok) assert.equal(result.value.name, "KYC Sentinel");
});

test("an app id is lower-case letters, digits and dashes — it appears in URLs and CI secrets", () => {
  for (const id of ["KYC", "kyc sentinel", "-kyc", "a".repeat(64), "", "kyc/../x"]) refused({ ...good, id }, "create", /id/);
});

test("an update does not take an id from the body — the URL names the app", () => {
  const result = parseAppInput({ ...good, id: "someone-else" }, "update");
  assert.ok(result.ok);
  if (result.ok) assert.equal(result.value.id, undefined);
});

test("SECURITY: a repository link must be http(s) — it becomes an href on every Dev page", () => {
  refused({ ...good, repoUrl: "javascript:alert(1)" }, "create", /repoUrl/);
  refused({ ...good, repoUrl: "file:///etc/passwd" }, "create", /repoUrl/);
});

test("a provider outside the catalogue is refused", () => {
  refused({ ...good, repoProvider: "bitbucket" }, "create", /repoProvider/);
});

test("a repository needs a provider, and a provider needs a repository", () => {
  refused({ ...good, repoProvider: null }, "create", /together/);
  refused({ ...good, repoUrl: null }, "create", /together/);
  const neither = parseAppInput({ ...good, repoUrl: null, repoProvider: null, defaultBranch: null }, "create");
  assert.ok(neither.ok, "an app may be registered before its repository is known");
});

test("a name and a branch are bounded", () => {
  refused({ ...good, name: "" }, "create", /name/);
  refused({ ...good, name: "x".repeat(201) }, "create", /name/);
  refused({ ...good, defaultBranch: "main; rm -rf /" }, "create", /defaultBranch/);
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
