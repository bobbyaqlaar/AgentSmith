// portal/test/devReadDb.test.ts — what the Dev pages read, against a real
// Postgres (portal phase 1, S5). The records go in through the same handler CI
// uses, so this also checks that what the ingest stores is what the pages read.
//
// Run: DATABASE_URL=postgresql://test:test@localhost:5432/test \
//        node --experimental-strip-types \
//        --experimental-loader=./test/ts-extension-loader.mjs \
//        test/devReadDb.test.ts

import assert from "node:assert/strict";

import { getPool } from "../lib/db.ts";
import { DEV_RECORD_SCHEMA } from "../lib/devIngest.ts";
import { handleDevIngest } from "../lib/devIngestHandler.ts";
import { commitsStartingWith, getDevDesign, listAwaitingApprovals, listDevApps, listDevCommits, listGateFailures } from "../lib/devRead.ts";
import { createIngestToken } from "../lib/ingestTokens.ts";
import { upsertTenant } from "../lib/tenants.ts";

if (!process.env.DATABASE_URL) {
  console.log("skipped - DATABASE_URL not set");
  process.exit(0);
}

const APP = `test-devread-${Date.now()}`;
let passed = 0;
async function test(name: string, fn: () => Promise<void>) {
  try {
    await fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

const sha = (n: number) => n.toString(16).padStart(40, "0");
const HASH = "d".repeat(64);
const design = (status: string, deviations: { id: string; approval_id: string | null }[]) => ({
  ref: ".agent-rfc/designs/x.md", path: ".agent-rfc/designs/x.md", resolved: true, title: "X", status,
  scope: ["src/**"], pillars: { P1: "applies" }, deviations: deviations.map((d) => ({ ...d, text_sha256: HASH })),
});
const commit = (n: number, time: string, extra: Record<string, unknown>) => ({
  commit: sha(n), parent: null, subject: `change ${n}`, author_name: "Ada", author_email: "a@x",
  committed_at: time, adopted: true, gated: true, verdict: "passed", errors: [], notes: [], repairs: [],
  design: null, review: null, ...extra,
});

await upsertTenant({ tenantId: APP, name: APP });
const token = await createIngestToken(APP, "test");
// At the head: design x as commit 4 left it, and design y — closed by a
// records commit that never cited it, so its last citation still says active.
const headDesigns = [
  { ...design("active", [{ id: "D1", approval_id: "A-1a2b3c4d" }, { id: "D2", approval_id: null }]) },
  { ...design("done", [{ id: "D9", approval_id: null }]), path: ".agent-rfc/designs/y.md", ref: undefined, title: "Y" },
];
const result = await handleDevIngest(`Bearer ${token}`, JSON.stringify({
  schema: DEV_RECORD_SCHEMA, head: sha(5), designs: headDesigns, commits: [
    commit(1, "2026-09-18T09:00:00Z", { design: design("active", [{ id: "D1", approval_id: null }, { id: "D2", approval_id: null }]) }),
    commit(2, "2026-09-18T10:00:00Z", { verdict: "failed", errors: ["missing Design: trailer"] }),
    commit(3, "2026-09-18T11:00:00Z", { verdict: "failed", errors: ["missing Review: trailer"] }),
    // The latest snapshot approves D1; D2 still awaits. And it repairs commit 2 only.
    commit(4, "2026-09-18T12:00:00Z", {
      design: design("active", [{ id: "D1", approval_id: "A-1a2b3c4d" }, { id: "D2", approval_id: null }]),
      repairs: [sha(2)],
    }),
    commit(5, "2026-09-18T12:30:00Z", {
      design: { ...design("active", [{ id: "D9", approval_id: null }]), path: ".agent-rfc/designs/y.md", title: "Y" },
    }),
  ],
}));
assert.equal(result.status, 200, JSON.stringify(result.body));

await test("a design is read as the head holds it, beside the commit that last cited it", async () => {
  const found = await getDevDesign(APP, ".agent-rfc/designs/x.md");
  assert.ok(found);
  assert.equal(found!.latest.sha, sha(4));
  assert.equal(found!.latest.design.deviations.find((d) => d.id === "D1")?.approvalId, "A-1a2b3c4d");
  assert.equal(found!.commits.length, 2);
});

await test("awaiting approval counts only what the head leaves unapproved, in active designs", async () => {
  const awaiting = await listAwaitingApprovals([APP]);
  assert.deepEqual(awaiting.map((a) => a.deviationId), ["D2"], "D9 is in a design closed at the head");
});

await test("status is the head's, not the last citation's", async () => {
  const found = await getDevDesign(APP, ".agent-rfc/designs/y.md");
  assert.equal(found?.latest.design.status, "done");
  assert.equal(found?.commits[0].design?.status, "active", "the commit keeps what was true then");
  assert.equal(found?.atHead, true);
});

await test("an older CI run posted late does not roll the designs back", async () => {
  const stale = await handleDevIngest(`Bearer ${token}`, JSON.stringify({
    schema: DEV_RECORD_SCHEMA, head: sha(3),
    designs: [{ ...design("active", []), path: ".agent-rfc/designs/y.md", title: "Y" }],
    commits: [commit(3, "2026-09-18T11:00:00Z", { verdict: "failed", errors: ["missing Review: trailer"] })],
  }));
  assert.equal(stale.status, 200);
  const found = await getDevDesign(APP, ".agent-rfc/designs/y.md");
  assert.equal(found?.latest.design.status, "done");
});

await test("a failure named in a later Repairs: trailer is repaired; the other is not", async () => {
  const failures = await listGateFailures(APP);
  const bySha = new Map(failures.map((f) => [f.failure.sha, f.repairedBy?.sha ?? null]));
  assert.equal(bySha.get(sha(2)), sha(4));
  assert.equal(bySha.get(sha(3)), null);
});

await test("the app summary agrees with the pages behind it", async () => {
  const [summary] = await listDevApps([APP]);
  assert.equal(summary.lastGated?.sha, sha(5));
  assert.equal(summary.activeDesigns, 1);
  assert.equal(summary.awaitingApproval, 1);
  assert.equal(summary.unrepaired, 1);
  assert.equal(summary.lastRun?.commits, 1, "the late run is still the last received");
});

await test("the changes list filters by verdict, newest first", async () => {
  const { commits } = await listDevCommits(APP, { verdict: "failed" });
  assert.deepEqual(commits.map((c) => c.sha), [sha(3), sha(2)]);
});

await test("a short hash resolves when it is unique, and says so when it is not", async () => {
  const distinct = "abcdef1234" + "5".repeat(30);
  const posted = await handleDevIngest(`Bearer ${token}`, JSON.stringify({
    schema: DEV_RECORD_SCHEMA, head: distinct, commits: [{ ...commit(0, "2026-09-18T08:00:00Z", {}), commit: distinct }],
  }));
  assert.equal(posted.status, 200);
  assert.deepEqual(await commitsStartingWith(APP, "abcdef1"), [distinct]);
  assert.deepEqual(await commitsStartingWith(APP, sha(4)), [sha(4)], "a full hash is its own match");
  assert.equal((await commitsStartingWith(APP, "0000000")).length, 2, "every seeded hash starts with zeros");
  assert.deepEqual(await commitsStartingWith(APP, "abc"), [], "under seven characters is not a hash");
  assert.deepEqual(await commitsStartingWith(APP, "%"), [], "a LIKE wildcard is not a hash either");
});

await test("an app with nothing received yet has no summary counts to invent", async () => {
  const empty = `${APP}-empty`;
  await upsertTenant({ tenantId: empty, name: empty });
  const [summary] = await listDevApps([empty]);
  assert.equal(summary.lastRun, null);
  assert.equal(summary.lastGated, null);
  await getPool().query(`DELETE FROM tenants WHERE tenant_id = $1`, [empty]);
});

await getPool().query(`DELETE FROM tenants WHERE tenant_id = $1`, [APP]);
await getPool().end();
console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
