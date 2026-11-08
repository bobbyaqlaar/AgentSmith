// portal/test/complianceState.test.ts — what the checklist shows, and which
// signatures a repository may send.
import assert from "node:assert/strict";
import { test } from "node:test";

import { checklist, mayDecide, parseAttestations, type AttestationRecord, type ObligationRow } from "../lib/complianceState";

const row = (id: string, cls: ObligationRow["class"]): ObligationRow => ({
  id, title: id, refs: {}, layer: "org", class: cls, phases: ["design"], mechanism: null, owner_role: "x",
  recurrence_days: 365, instructions: "i", evidence: "e", blocks: ["production"], profiles: ["dubai-gov"],
});
const signed = (over: Partial<AttestationRecord>): AttestationRecord => ({
  id: "T-1", obligation: "OB-A", actor: "a", role: "r", evidence: "e", attested_at: "2026-11-01T00:00:00Z",
  expires_at: null, note: "", channel: "tty", ...over,
});
const NOW = new Date("2026-11-08T00:00:00Z");
const stateOf = (records: AttestationRecord[]) => checklist([row("OB-A", "attested")], records, NOW)[0].state;

test("no signature reads as missing", () => assert.equal(stateOf([]), "missing"));
test("a live signature reads as signed", () => assert.equal(stateOf([signed({ expires_at: "2027-11-01T00:00:00Z" })]), "signed"));
test("one inside thirty days reads as expiring", () => assert.equal(stateOf([signed({ expires_at: "2026-11-20T00:00:00Z" })]), "expiring"));
test("a lapsed one reads as expired", () => assert.equal(stateOf([signed({ expires_at: "2026-11-07T00:00:00Z" })]), "expired"));
test("the newest signature decides", () => {
  assert.equal(stateOf([signed({ expires_at: "2026-11-07T00:00:00Z" }), signed({ id: "T-2", attested_at: "2026-11-07T00:00:00Z", expires_at: "2027-11-07T00:00:00Z" })]), "signed");
});
test("a mechanism-backed row is automatic", () => assert.equal(checklist([row("OB-B", "verified")], [], NOW)[0].state, "automatic"));

const known = new Set(["OB-A"]);
test("a good batch parses", () => assert.equal(parseAttestations({ attestations: [signed({})] }, known).ok, true));
for (const [name, bad] of Object.entries({
  "an unknown obligation": { obligation: "OB-Z" }, "no evidence": { evidence: "" }, "a portal channel": { channel: "portal" },
  "a date that does not parse": { attested_at: "soon" }, "a non-string expiry": { expires_at: 7 },
})) {
  test(`one record with ${name} refuses the batch`, () => {
    assert.equal(parseAttestations({ attestations: [signed({}), { ...signed({}), ...bad }] }, known).ok, false);
  });
}

test("a person does not decide their own request, whatever the case", () => {
  assert.equal(mayDecide("Rita@X", "rita@x"), false);
  assert.equal(mayDecide("omar@x", "rita@x"), true);
  assert.equal(mayDecide("omar@x", null), true);
});
