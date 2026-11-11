// portal/test/scripts.test.ts — every test file is run by an npm script CI runs
// (the 4.1.0 release review, R23), and the scripts that exist run.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf-8"));
const run = `${pkg.scripts.test} ${pkg.scripts["test:db"]}`;

test("no test file is left out of npm test and npm run test:db", () => {
  const files = readdirSync(new URL("../test/", import.meta.url)).filter((name) => name.endsWith(".test.ts"));
  const missing = files.filter((name) => !run.includes(`test/${name}`));
  assert.deepEqual(missing, []);
});

test("no script calls `next lint`, which Next.js 16 removed (R27)", () => {
  assert.ok(!Object.values(pkg.scripts as Record<string, string>).some((s) => /\bnext lint\b/.test(s)));
});
