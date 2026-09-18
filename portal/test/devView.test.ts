// portal/test/devView.test.ts — what the Dev pages compute from stored records
// (portal phase 1, S5): links into an app's repository, how fresh its data is,
// and which failures are still unrepaired. Pure, so it runs without a database.
//
// Run (from portal/):
//   node --experimental-strip-types \
//     --experimental-loader=./test/ts-extension-loader.mjs \
//     test/devView.test.ts

import assert from "node:assert/strict";

import { STALE_AFTER_HOURS, commitUrl, fileUrl, freshness, unrepairedFailures } from "../lib/devView.ts";

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

const SHA = "0123456789abcdef0123456789abcdef01234567";
const github = { repoUrl: "https://github.com/acme/app.git/", repoProvider: "github" as const };
const gitlab = { repoUrl: "https://gitlab.example.com/acme/app", repoProvider: "gitlab" as const };

test("links go to the commit, not a branch — files move, a commit does not", () => {
  assert.equal(commitUrl(github, SHA), `https://github.com/acme/app/commit/${SHA}`);
  assert.equal(fileUrl(github, SHA, ".agent-rfc/designs/x.md"), `https://github.com/acme/app/blob/${SHA}/.agent-rfc/designs/x.md`);
  assert.equal(commitUrl(gitlab, SHA), `https://gitlab.example.com/acme/app/-/commit/${SHA}`);
  assert.equal(fileUrl(gitlab, SHA, "a b/c.md"), `https://gitlab.example.com/acme/app/-/blob/${SHA}/a%20b/c.md`);
});

test("SECURITY: a repository URL that is not http(s) yields no link at all", () => {
  assert.equal(commitUrl({ repoUrl: "javascript:alert(1)", repoProvider: "github" }, SHA), null);
  assert.equal(fileUrl({ repoUrl: "javascript:alert(1)", repoProvider: "github" }, SHA, "x.md"), null);
});

test("an app with no repository registered yields no link, not a guess", () => {
  assert.equal(commitUrl({ repoUrl: null, repoProvider: null }, SHA), null);
  assert.equal(commitUrl({ repoUrl: "https://github.com/a/b", repoProvider: null }, SHA), null);
});

test("freshness has three answers, and 'never' is not 'stale'", () => {
  const now = new Date("2026-09-18T12:00:00Z");
  assert.equal(freshness(null, now), "never");
  assert.equal(freshness("2026-09-18T11:00:00Z", now), "fresh");
  const old = new Date(now.getTime() - (STALE_AFTER_HOURS + 1) * 3600_000).toISOString();
  assert.equal(freshness(old, now), "stale");
});

test("a failure is unrepaired until a later commit names it in Repairs:", () => {
  const commits = [
    { sha: "a".repeat(40), verdict: "failed" as const, repairs: [] },
    { sha: "b".repeat(40), verdict: "failed" as const, repairs: [] },
    { sha: "c".repeat(40), verdict: "passed" as const, repairs: ["a".repeat(40)] },
  ];
  assert.deepEqual(unrepairedFailures(commits).map((c) => c.sha), ["b".repeat(40)]);
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
