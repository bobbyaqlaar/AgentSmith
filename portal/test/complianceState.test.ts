// portal/test/complianceState.test.ts — what the checklist shows, and which
// signatures a repository may send.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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

// ── The 4.1.0 release review: R15, R29 ──

test("a recurring signature expires on its period, whatever expires_at says (R15)", () => {
  const old = signed({ attested_at: "2020-01-01T00:00:00Z", expires_at: null });
  assert.equal(stateOf([old]), "expired");
  const stretched = signed({ attested_at: "2020-01-01T00:00:00Z", expires_at: "2299-01-01T00:00:00Z" });
  assert.equal(stateOf([stretched]), "expired");
});
test("a signature dated in the future does not count (R15)", () => {
  assert.equal(stateOf([signed({ attested_at: "2027-01-01T00:00:00Z" })]), "missing");
});
test("the requester is compared as an email, trimmed (R29)", () => {
  assert.equal(mayDecide("fatima@entity.ae", " Fatima@Entity.AE "), false);
  assert.equal(mayDecide("omar@entity.ae", " fatima@entity.ae "), true);
});
test("a requester that is not an email cannot be told apart, so nobody may decide (R29)", () => {
  assert.equal(mayDecide("fatima@entity.ae", "fatima"), false);
});

// ── The 4.1.0 review's second pass: P2-R20 ──
// The cases the port's test reads too (scripts/test/test_compliance_port.py), so the two cannot drift apart.

const SIGNATURES = JSON.parse(readFileSync(new URL("../../fixtures/compliance/signature_cases.json", import.meta.url), "utf-8")).cases as Array<{
  name: string; recurrence_days: number | null; now: string; counts: string | null; state: string;
  records: Array<{ id: string; attested_at: string; expires_at: string | null }>;
}>;

for (const c of SIGNATURES) {
  test(`shared signature case: ${c.name}`, () => {
    const row = { id: "OB-X", title: "x", refs: {}, layer: "app" as const, class: "attested" as const, phases: ["operate" as const],
                  mechanism: null, owner_role: "r", recurrence_days: c.recurrence_days, instructions: "i", evidence: "e",
                  blocks: ["production" as const], profiles: ["dubai-gov"] };
    const records = c.records.map((r) => ({ ...r, obligation: "OB-X", actor: "x@y", role: "r", evidence: "e", note: "", channel: "tty" as const }));
    const [result] = checklist([row], records, new Date(c.now));
    assert.equal(result.state, c.state);
    if (c.state === "signed" || c.state === "expiring") assert.equal(result.latest?.id, c.counts);
  });
}
