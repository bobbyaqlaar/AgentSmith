// portal/test/wireContract.test.ts — an absent field must say WHY it is absent.
//
// The portal reads a fleet of tenants that IT does not control the release
// cadence of. A NULL `cost_usd` means either "this framework version never
// reported cost" or "a current tenant should have and did not" — a fact about
// the fleet and a fault, rendered identically. lib/wireContract.ts splits them,
// and these lock in the split.
//
// The third state is the one worth guarding. Two-state answers are how this
// codebase keeps producing pillar-15 defects, so `emits()` returns
// yes/no/unknown and `unknown` must never collapse into either.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  FIRST_VERSIONED_RELEASE,
  emits,
  explainAbsent,
  parseVersion,
  versionBreakdown,
} from "../lib/wireContract.ts";

const PORTAL = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(PORTAL, "..");

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

test("no version at all means the row predates the fields, not that they are missing", () => {
  // The load-bearing inference: framework_version began being reported by the
  // same release that added tokens, cost and trace id, so its absence dates
  // the row without any version table being consulted.
  assert.equal(emits(null, "costUsd"), "no");
  assert.equal(emits(undefined, "inputTokens"), "no");
});

test("a released version at or above the threshold should have reported it", () => {
  assert.equal(emits(FIRST_VERSIONED_RELEASE, "costUsd"), "yes");
  assert.equal(emits("1.4.2", "traceId"), "yes");
  assert.equal(emits("2.0.0", "inputTokens"), "yes");
});

test("a released version below the threshold could not have", () => {
  assert.equal(emits("1.2.0", "costUsd"), "no");
  assert.equal(emits("1.1.9", "traceId"), "no");
  assert.equal(emits("0.9.0", "outputTokens"), "no");
});

test("a +src build is unknown, not assumed from its number", () => {
  // A working copy sitting between two releases. Its number says which release
  // it descends from and nothing about what it contains — main carried the
  // token fields for weeks while pyproject.toml still said 1.2.0.
  assert.equal(emits("1.2.0+src", "costUsd"), "unknown");
  assert.equal(emits("9.9.9+src", "costUsd"), "unknown");
});

test("an unparseable version is unknown, and is not treated as absent", () => {
  // Distinct from null on purpose: something reported a version and we cannot
  // read it, which is a different situation from nothing reporting one.
  assert.equal(emits("nightly-build", "costUsd"), "unknown");
  assert.equal(emits("unknown", "costUsd"), "unknown");
  assert.notEqual(emits("nightly-build", "costUsd"), emits(null, "costUsd"));
});

test("explainAbsent stays silent when the absence is a real gap", () => {
  // "yes" means the version should have reported it. The caller owns that
  // sentence — this module must not paper over a fault with an excuse.
  assert.equal(explainAbsent("1.3.0", "costUsd"), null);
});

test("explainAbsent names the version when the version is the reason", () => {
  assert.match(String(explainAbsent("1.2.0", "costUsd")), /not reported by AgentSmith 1\.2\.0/);
  assert.match(String(explainAbsent(null, "costUsd")), /pre-1\.3\.0/);
  assert.match(String(explainAbsent("1.2.0+src", "costUsd")), /cannot tell/);
});

test("parseVersion distinguishes a release from a working copy", () => {
  assert.deepEqual(parseVersion("1.2.0"), { major: 1, minor: 2, patch: 0, fromSource: false });
  assert.deepEqual(parseVersion("1.2.0+src"), { major: 1, minor: 2, patch: 0, fromSource: true });
  assert.equal(parseVersion("1.2"), null);
  assert.equal(parseVersion(""), null);
});

test("version ordering is numeric, not lexicographic", () => {
  // "1.10.0" < "1.9.0" as strings. A fleet spanning a minor-version rollover
  // is exactly when this matters.
  assert.equal(emits("1.10.0", "costUsd"), "yes");
  assert.equal(emits("1.2.10", "costUsd"), "no");
});

test("versionBreakdown gives IT the fleet view, with the unversioned bucket named", () => {
  const rows = versionBreakdown(["1.3.0", "1.3.0", null, "1.2.0", null, null]);
  assert.deepEqual(rows, [
    { version: "pre-1.3.0", count: 3 },
    { version: "1.3.0", count: 2 },
    { version: "1.2.0", count: 1 },
  ]);
});

test("versionBreakdown does not silently drop the unversioned rows", () => {
  // A count that omits what it could not classify is the unattributed-aggregate
  // shape: the number is not ambiguous, it is incomplete, and a reader cannot tell.
  const rows = versionBreakdown([null, null]);
  assert.equal(rows.reduce((n, r) => n + r.count, 0), 2);
});

// ── The threshold is a guess until the release is cut ────────────────────────

test("FIRST_VERSIONED_RELEASE is still ahead of the newest shipped version", () => {
  // It names the PENDING release. Once that release is cut, the CHANGELOG's
  // compatibility matrix gains a row for it — and if this constant is still
  // pointing at something newer than the newest shipped row, or has fallen
  // behind it, every "not reported by this version" answer above is wrong.
  const changelog = readFileSync(join(REPO, "CHANGELOG.md"), "utf8");
  const rows = [...changelog.matchAll(/^\| (\d+\.\d+)\.x \|/gm)].map((m) => m[1]);
  assert.ok(rows.length > 0, "no compatibility-matrix rows found in CHANGELOG.md");

  const [major, minor] = FIRST_VERSIONED_RELEASE.split(".").map(Number);
  const newest = rows[0].split(".").map(Number);
  const pendingIsNewer =
    major > newest[0] || (major === newest[0] && minor > newest[1]);
  const pendingIsShipped =
    major === newest[0] && minor === newest[1];
  assert.ok(
    pendingIsNewer || pendingIsShipped,
    `FIRST_VERSIONED_RELEASE=${FIRST_VERSIONED_RELEASE} is older than the ` +
      `newest shipped matrix row ${rows[0]}.x — the wire contract table has ` +
      `fallen behind the releases it describes`,
  );
});

test("the ingest route and the column agree that the version is nullable", () => {
  // Three places have to hold the same nullability, and the database is the one
  // that cannot be talked out of it.
  const schema = readFileSync(join(PORTAL, "db", "schema.sql"), "utf8");
  assert.match(schema, /framework_version TEXT(?!\s+NOT NULL)/);
  assert.match(
    schema,
    /ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS framework_version TEXT;/,
    "a deployed portal only gains the column from the ALTER, never from CREATE TABLE",
  );
});

console.log(`\nwire contract: ${passed} checks passed`);
