// portal/test/hitl.test.ts — the reviewers' queue (the 4.1.0 release review, R21).
import assert from "node:assert/strict";
import { test } from "node:test";

import { decisionMessage, PENDING, sendStopControl, stopState } from "../lib/hitl";

test("only a timeout recorded after a request hides it (R21)", () => {
  const sql = PENDING.replace(/\s+/g, " ");
  assert.match(sql, /t\.record_id > r\.record_id/);
});

test("a decision names the request it answers, not only the input (P2-R14)", () => {
  const gate = { recordId: 41, gateId: "g", workflowId: "w", inputSha256: "a".repeat(64) };
  const message = decisionMessage(gate, { approved: true, actor: "b@x", role: "hitl_reviewer", rationale: "ok" },
                                  new Date("2026-11-12T00:00:00Z"));
  assert.deepEqual(message, {
    gate_id: "g", workflow_id: "w", approved: true, actor: "b@x", role: "hitl_reviewer", rationale: "ok",
    payload_sha256: "a".repeat(64), decided_at: "2026-11-12T00:00:00.000Z", request_record_id: 41,
  });
});

// ── P2-R19 (.agent-rfc/designs/vector-ids-per-tenant-and-stop-state.md) ──
const at = (iso: string) => new Date(iso);

test("the app's record decides the state, from the portal or a terminal (P2-R19)", () => {
  const terminalStop = { action: "stop", actor: "ops@x", reason: "bad output", receivedAt: at("2026-11-13T10:00:00Z") };
  assert.deepEqual(stopState(terminalStop, null), { stopped: true, actor: "ops@x", reason: "bad output", recorded: true, sent: null });
  assert.equal(stopState({ ...terminalStop, action: "resume" }, null).stopped, false);
  assert.deepEqual(stopState(null, null), { stopped: false, actor: null, reason: null, recorded: false, sent: null });
});

test("a portal action newer than the app's record is shown as sent, not as done (P2-R19)", () => {
  const record = { action: "resume", actor: "a@x", reason: "", receivedAt: at("2026-11-13T10:00:00Z") };
  const later = { action: "stop", actor: "b@x", at: at("2026-11-13T10:05:00Z") };
  const state = stopState(record, later);
  assert.equal(state.stopped, false);
  assert.deepEqual(state.sent, { action: "stop", actor: "b@x" });
  assert.equal(stopState(record, { ...later, at: at("2026-11-13T09:00:00Z") }).sent, null);
});

test("a stop the app refuses is not audited (P2-R19)", async () => {
  const done: string[] = [];
  const deps = {
    withTransaction: async (_name: string, work: (client: unknown) => Promise<void>) => {
      try { await work({}); done.push("commit"); } catch (err) { done.push("rollback"); throw err; }
    },
    appendAuditEvent: async () => { done.push("audit"); },
    postSigned: async () => { done.push("post"); throw new Error("the app's webhook answered 502"); },
  };
  await assert.rejects(sendStopControl(deps, { tenantId: "t", action: "stop", scope: "*", reason: "r", actor: "a@x" }), /502/);
  assert.deepEqual(done, ["audit", "post", "rollback"]);
});
