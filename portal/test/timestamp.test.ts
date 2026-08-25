// portal/test/timestamp.test.ts — the formatter must give the same answer
// everywhere, which is the property the three inline calls it replaced did not
// have.
//
// It imports lib/formatTime.ts and not the component: `--experimental-strip-types`
// cannot load a .tsx, so logic parked next to JSX is logic no suite here can
// reach. That is why the rule lives in lib/.

import assert from "node:assert/strict";

import { formatUtc } from "../lib/formatTime.ts";

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

test("the same instant formats identically whatever TZ the process is in", () => {
  // The hydration bug in one assertion: a server component formatted in the
  // container's zone and a client component in the browser's, so the same
  // value produced two strings and React patched the difference.
  const iso = "2026-08-25T14:03:12.482Z";
  const original = process.env.TZ;
  const seen = new Set<string>();
  try {
    for (const tz of ["UTC", "Asia/Dubai", "America/Los_Angeles", "Pacific/Kiritimati"]) {
      process.env.TZ = tz;
      seen.add(formatUtc(iso));
    }
  } finally {
    if (original === undefined) delete process.env.TZ;
    else process.env.TZ = original;
  }
  assert.equal(seen.size, 1, `formatting varied by timezone: ${[...seen].join(" | ")}`);
  assert.equal([...seen][0], "2026-08-25 14:03:12 UTC");
});

test("the zone is stated, not implied", () => {
  assert.ok(formatUtc("2026-01-01T00:00:00Z").endsWith(" UTC"));
});

test("a Date and its ISO string agree", () => {
  // pg hands back a Date for timestamptz while the TypeScript types on these
  // rows say `string`, so both arrive in practice.
  const iso = "2026-08-25T14:03:12.482Z";
  assert.equal(formatUtc(new Date(iso)), formatUtc(iso));
});

test("an unparseable value renders as absent, not as 'Invalid Date'", () => {
  assert.equal(formatUtc("not a date"), "—");
  assert.equal(formatUtc(new Date("nonsense")), "—");
});

console.log(`\n${passed} passed`);
