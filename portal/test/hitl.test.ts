// portal/test/hitl.test.ts — the reviewers' queue (the 4.1.0 release review, R21).
import assert from "node:assert/strict";
import { test } from "node:test";

import { decisionMessage, PENDING } from "../lib/hitl";

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
