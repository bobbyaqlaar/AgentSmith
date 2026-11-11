// portal/test/submitOnce.test.ts — one click, one request, and an answer either way
// (the 4.1.0 release review, R28).
import assert from "node:assert/strict";
import { test } from "node:test";

import { submitOnce } from "../lib/submitOnce";

test("a second click while the first is in flight sends nothing", async () => {
  let sent = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const state = { busy: false };
  const first = submitOnce(state, async () => { sent += 1; await gate; });
  const second = await submitOnce(state, async () => { sent += 1; });
  assert.equal(second.ok, false);
  release();
  assert.equal((await first).ok, true);
  assert.equal(sent, 1);
  assert.equal(state.busy, false);
});

test("a network failure is an answer, not silence", async () => {
  const result = await submitOnce({ busy: false }, async () => { throw new TypeError("fetch failed"); });
  assert.deepEqual(result, { ok: false, error: "fetch failed" });
});

test("a declined confirmation sends nothing", async () => {
  let sent = 0;
  const result = await submitOnce({ busy: false }, async () => { sent += 1; }, () => false);
  assert.equal(result.ok, false);
  assert.equal(sent, 0);
});
