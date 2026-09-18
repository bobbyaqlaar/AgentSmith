// portal/test/devIngest.test.ts — validating the Dev ingest (portal phase 1, S3).
//
// The body is what `process_gate.py ci --json` wrote, sent by an app's CI. It
// is data from outside the portal, so it is validated before anything is
// stored — and a body that fails anywhere stores nothing, not the valid half.
//
// Run (from portal/):
//   node --experimental-strip-types \
//     --experimental-loader=./test/ts-extension-loader.mjs \
//     test/devIngest.test.ts

import assert from "node:assert/strict";

import { DEV_LIMITS, DEV_RECORD_SCHEMA, DEV_VERDICTS, parseDevIngest } from "../lib/devIngest.ts";

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

const SHA = "a".repeat(40);
const PARENT = "b".repeat(40);

function commit(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    commit: SHA,
    parent: PARENT,
    subject: "feat: x",
    author_name: "Ada",
    author_email: "ada@example.com",
    committed_at: "2026-09-18T10:00:00+04:00",
    adopted: true,
    gated: true,
    verdict: "passed",
    errors: [],
    notes: [],
    repairs: [],
    design: {
      ref: ".agent-rfc/designs/x.md",
      path: ".agent-rfc/designs/x.md",
      resolved: true,
      title: "X",
      status: "active",
      scope: ["scripts/**"],
      pillars: { P1: "applies", P9: "n/a" },
      deviations: [{ id: "D1", text_sha256: "c".repeat(64), approval_id: null }],
    },
    review: {
      ref: ".agent-rfc/reviews/x.md",
      path: ".agent-rfc/reviews/x.md",
      resolved: true,
      passes: [{ n: 1, findings: 0 }],
      signed_off: true,
      kg_query: "kg:0123456789ab",
    },
    ...overrides,
  };
}

function body(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema: DEV_RECORD_SCHEMA,
    generated_at: "2026-09-18T10:01:00Z",
    base: PARENT,
    head: SHA,
    range_caveat: null,
    commits: [commit()],
    ...overrides,
  };
}

function refused(value: unknown, why: RegExp) {
  const result = parseDevIngest(value);
  assert.equal(result.ok, false, "expected a refusal");
  if (!result.ok) assert.match(result.error, why);
}

test("a record as the gate writes it is accepted", () => {
  const result = parseDevIngest(body({ ci_run_url: "https://github.com/o/r/actions/runs/1" }));
  assert.ok(result.ok, result.ok ? "" : result.error);
  if (!result.ok) return;
  assert.equal(result.value.head, SHA);
  assert.equal(result.value.ciRunUrl, "https://github.com/o/r/actions/runs/1");
  const [c] = result.value.commits;
  assert.equal(c.sha, SHA);
  assert.equal(c.verdict, "passed");
  assert.equal(c.design?.deviations[0].id, "D1");
  assert.equal(c.review?.kgQuery, "kg:0123456789ab");
});

test("the verdicts are the five the gate emits", () => {
  assert.deepEqual([...DEV_VERDICTS], ["passed", "failed", "passed_with_notes", "not_gated", "before_adoption"]);
});

test("a schema this portal does not know is refused by number", () => {
  refused(body({ schema: 2 }), /schema 2/);
  refused(body({ schema: undefined }), /schema/);
});

test("anything but an object is refused", () => {
  refused(null, /object/);
  refused([], /object/);
  refused("{}", /object/);
});

test("a commit that is not a hash is refused, naming the commit", () => {
  refused(body({ commits: [commit({ commit: "HEAD" })] }), /commits\[0\]\.commit/);
  refused(body({ head: "main" }), /head/);
});

test("an unknown verdict is refused — the portal does not invent one", () => {
  refused(body({ commits: [commit({ verdict: "approved" })] }), /verdict/);
});

test("the limits are enforced, not assumed", () => {
  refused(body({ commits: Array.from({ length: DEV_LIMITS.commits + 1 }, () => commit()) }), /at most/);
  refused(body({ commits: [commit({ subject: "x".repeat(DEV_LIMITS.subject + 1) })] }), /subject/);
  refused(body({ commits: [commit({ errors: ["x".repeat(DEV_LIMITS.text + 1)] })] }), /errors/);
  refused(body({ commits: [commit({ notes: Array.from({ length: DEV_LIMITS.list + 1 }, () => "n") })] }), /notes/);
});

test("a list that must hold strings holds only strings", () => {
  refused(body({ commits: [commit({ errors: [{ html: "<b>" }] })] }), /errors/);
  refused(body({ commits: [commit({ repairs: ["not-a-sha"] })] }), /repairs/);
});

test("a design or review that did not resolve is kept, with its reason", () => {
  const result = parseDevIngest(body({ commits: [commit({
    design: { ref: "x.md", path: null, resolved: false, reason: "x.md does not exist in this commit" },
    review: null,
  })] }));
  assert.ok(result.ok);
  if (!result.ok) return;
  assert.equal(result.value.commits[0].design?.resolved, false);
  assert.match(result.value.commits[0].design?.reason ?? "", /does not exist/);
  assert.equal(result.value.commits[0].review, null);
});

test("keys the gate does not write are dropped, not stored", () => {
  const result = parseDevIngest(body({ commits: [commit({ smuggled: "x", design: {
    ...(commit().design as object), extra: "<script>",
  } })] }));
  assert.ok(result.ok);
  if (!result.ok) return;
  assert.ok(!("smuggled" in result.value.commits[0]));
  assert.ok(!("extra" in (result.value.commits[0].design as object)));
});

test("a CI run link that is not http(s) is refused", () => {
  refused(body({ ci_run_url: "javascript:alert(1)" }), /ci_run_url/);
});

test("a pillar kind outside the four and `unrecognised` is refused", () => {
  const design = { ...(commit().design as object), pillars: { P1: "maybe" } };
  refused(body({ commits: [commit({ design })] }), /pillars/);
});

test("a commit time that is not a time is refused; an empty one is none", () => {
  refused(body({ commits: [commit({ committed_at: "yesterday" })] }), /committed_at/);
  const result = parseDevIngest(body({ commits: [commit({ committed_at: "" })] }));
  assert.ok(result.ok);
  if (result.ok) assert.equal(result.value.commits[0].committedAt, null);
});

test("the designs at the head are optional, but when sent each must have a path", () => {
  const withDesigns = parseDevIngest(body({ designs: [{ path: "a.md", title: "A", status: "done", scope: [], pillars: {}, deviations: [] }] }));
  assert.ok(withDesigns.ok);
  if (withDesigns.ok) assert.equal(withDesigns.value.designs?.[0].path, "a.md");
  const without = parseDevIngest(body());
  assert.ok(without.ok);
  if (without.ok) assert.equal(without.value.designs, null, "absent means leave the snapshot alone, not empty it");
  refused(body({ designs: [{ title: "no path" }] }), /designs\[0\]\.path/);
  refused(body({ designs: Array.from({ length: DEV_LIMITS.designs + 1 }, () => ({ path: "a.md" })) }), /at most/);
});

console.log(`\n${passed} passed`);
process.exit(process.exitCode || 0);
