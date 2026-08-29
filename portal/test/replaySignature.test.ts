/**
 * portal/test/replaySignature.test.ts — the replay webhook's outbound signatures.
 *
 * The portal signs; runtime/replay_webhook_server.py verifies. They are
 * operated by different people and ship on different cadences, so this asserts
 * the wire shape both sides agreed on rather than "a signature was produced".
 *
 * Legacy is an HMAC over the body alone and never expires, so a captured
 * request stays replayable. v2 signs `timestamp.body` and the receiver rejects
 * anything outside a five-minute window. Both are sent so either side can be
 * upgraded first.
 */

import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { replaySignatureHeaders } from "../lib/dlq.ts";

const SECRET = "shared-secret";
const BODY = JSON.stringify({ taskId: "t-1", payload: { a: 1 } });
const NOW_MS = 1_756_500_000_000;

let passed = 0;
function check(name: string, fn: () => void) {
  fn();
  console.log(`ok - ${name}`);
  passed += 1;
}

check("both signature shapes are sent, so either side can upgrade first", () => {
  const h = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  assert.ok(h["X-Replay-Signature"], "legacy header missing — old receivers 401");
  assert.ok(h["X-Replay-Timestamp"], "timestamp header missing");
  assert.ok(h["X-Replay-Signature-V2"], "v2 header missing");
});

check("the timestamp is whole seconds, which is what the receiver parses", () => {
  const h = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  assert.equal(h["X-Replay-Timestamp"], "1756500000");
  assert.match(h["X-Replay-Timestamp"], /^\d+$/);
});

check("v2 signs `timestamp.body`, not the body alone", () => {
  const h = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  const expected =
    "sha256=" +
    createHmac("sha256", SECRET).update(`1756500000.${BODY}`).digest("hex");
  assert.equal(h["X-Replay-Signature-V2"], expected);
  assert.notEqual(
    h["X-Replay-Signature-V2"],
    h["X-Replay-Signature"],
    "v2 equals legacy — the timestamp is not in the signed material"
  );
});

check("legacy stays exactly what it was, byte for byte", () => {
  const h = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  const expected = "sha256=" + createHmac("sha256", SECRET).update(BODY).digest("hex");
  assert.equal(h["X-Replay-Signature"], expected);
});

check("the v2 signature changes with the timestamp", () => {
  const a = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  const b = replaySignatureHeaders(SECRET, BODY, NOW_MS + 60_000);
  assert.notEqual(a["X-Replay-Signature-V2"], b["X-Replay-Signature-V2"]);
  assert.equal(a["X-Replay-Signature"], b["X-Replay-Signature"], "legacy is time-independent, which is the flaw it has");
});

check("a different secret produces a different signature", () => {
  const a = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  const b = replaySignatureHeaders("other-secret", BODY, NOW_MS);
  assert.notEqual(a["X-Replay-Signature-V2"], b["X-Replay-Signature-V2"]);
});

check("the signature covers the body", () => {
  const a = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  const b = replaySignatureHeaders(SECRET, JSON.stringify({ taskId: "t-2" }), NOW_MS);
  assert.notEqual(a["X-Replay-Signature-V2"], b["X-Replay-Signature-V2"]);
});

check("the exact bytes the Python receiver expects for a known input", () => {
  // Pinned cross-language. runtime/test/test_replay_webhook_signature.py builds
  // the same value; if either side changes its derivation, one of the two fails.
  const h = replaySignatureHeaders(SECRET, BODY, NOW_MS);
  assert.equal(
    h["X-Replay-Signature-V2"],
    "sha256=" +
      createHmac("sha256", SECRET).update(`1756500000.${BODY}`).digest("hex")
  );
});

console.log(`\nreplay signature: ${passed} checks passed`);
