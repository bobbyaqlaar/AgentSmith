// portal/test/hitl.test.ts — the reviewers' queue (the 4.1.0 release review, R21).
import assert from "node:assert/strict";
import { test } from "node:test";

import { PENDING } from "../lib/hitl";

test("only a timeout recorded after a request hides it (R21)", () => {
  const sql = PENDING.replace(/\s+/g, " ");
  assert.match(sql, /t\.record_id > r\.record_id/);
});
