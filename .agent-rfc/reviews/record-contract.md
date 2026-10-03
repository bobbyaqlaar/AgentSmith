# Review — record-contract (C3)

Design: `.agent-rfc/designs/record-contract.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 5

1. **The published schema accepted what the portal refuses.** Pydantic rendered the pillars map as
   `patternProperties` alone, which lets any other key through; `portal/lib/devIngest.ts` refuses a key
   that is not a pillar. A sender that validated against the contract could still be refused by the
   portal — the drift the contract exists to end, inside the contract. The field now carries
   `propertyNames`, so the schema refuses `Q1` as the portal does.

2. **The gate grew a dependency its test layout did not carry.** Validating in the parts the record is
   sent in imports `send_dev_record`, and the harness's copy of the gate (`GATE_FILES`) did not
   include it: nine record tests failed with `ModuleNotFoundError`. Every real layout carries it — the
   install, a vendored `scripts/`, the provider's own checkout — and the gate already used it to send;
   it is now listed as one of the gate's files, with why.

3. **The sender suite could not show it fails anything.** AgentSmith passing it proves nothing about a
   suite whose checks might always be true. A stub provider that always allows and never sends is now
   run through it, and the test asserts exactly which four checks fail — so a check that stopped
   checking would change the set. Mutations on three of those checks are caught by it.

4. **The receiver suite, likewise.** A strict stub portal (validating as the contract says) must pass
   and a lax one (storing anything) must fail; a mutation that passes every case is caught.

5. **Two hygiene slips.** The redirect handler was declared through `__import__(...)` rather than an
   import; a mutation's search string ran past the 120-character line limit — the source line it
   targets was split into a named value instead of wrapping the string.

The portal side is TypeScript, which `scripts/mutation_check.py` does not drive: mutated by hand —
the commit limit set to 400, a verdict dropped from the catalogue — each caught by
`recordContract.test.ts`, the file restored and compared.

## Pass 2 — findings: 1

The full suite after pass 1: 2 failed, 2120 passed — the gate contract's own conformance, v2 and v3.

1. **The gate had been building records no receiver could store, and validation exposed it.** For a
   new branch (an all-zeros base) or a base a force-push removed, `_range_commits` judged the head
   alone — and returned it as the caller spelled it. Asked about `after`, the record's `commit` was
   the string `after`. GitHub always passes a hash, so CI never hit it; any caller passing a ref did,
   and the portal would have refused the record with a 400 nobody connected to the gate. With the
   record now validated before it leaves, the gate refused itself — the new-branch conformance case
   flipped to `deny` with the exact field. The head is resolved to its commit hash;
   `test_a_range_named_by_ref_records_commit_hashes` pins it, and a mutation that skips the resolve
   is caught. Conformance back to 10/10 and 15/15.

## Pass 3 — findings: 0

The full suite: 2123 passed, 10 skipped. The portal's suites: every pure test, and every database
test against a fresh Postgres, including the receiver's 9/9 contract cases. Re-read the protocol
against `send_dev_record.py`, `devIngestHandler.ts` and `devStore.ts` line by line — each answer, the
loopback rule, the redirect, the parts, the newest-wins store — and the CHANGELOG, manual and
`process-gates.md` against the code. Every mutation target in the catalogue matches.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one model generates the schema; the gate's verdict catalogue is the model's; the portal's hand-written validator is pinned to the published file rather than to a second copy; the case-body rule exists twice (Python runner, TypeScript test helper) because each side's tests need it in its own language, and both apply the same `cases.json`.
Group 2 · Quality / safety — [x] checked — 10 Python tests and 2 portal test files; 6 mutations in `record_contract`, all caught; two portal mutations by hand, caught; conformance: AgentSmith's sender 5/5, its portal 9/9, and a bad sender and a bad receiver each judged non-conformant.
Group 3 · Architecture / hygiene — [x] checked — validation sits where the record is built; the sender stays standard-library only (its chunk size pinned to the contract instead of importing the model); no tenant file changes.
Group 4 · Process — [x] checked — design before code; the backlog row moved, an archive entry written, the protocol declared as reference documentation.
Group 5 · Intuitive UI — [x] checked — a record the contract would refuse fails the run with the field and the reason, in the gate's report.
Group 6 · Signal integrity — [x] checked — refused, unwell and not configured stay three answers on both sides; the latent ref-in-record defect now fails loudly instead of as a portal 400.
Group 7 · Auth & session integrity — [x] checked — the token only over https or loopback and never across a redirect, checked against a live sender; never in a case file or report.

Tests added: `scripts/test/test_record_contract.py` (10); `portal/test/recordContract.test.ts`, `portal/test/recordContractDb.test.ts`, `portal/test/recordCases.ts`; `scripts/send_dev_record.py` added to `GATE_FILES` in `test_process_gate.py`; the regex pin removed from `test_dev_record.py`.
Mutation-checked: `python3 scripts/mutation_check.py record_contract` — 6 caught; portal by hand — the commit limit and a verdict, each caught.
Fixtures re-pinned: `contract/record/v1/` written new; `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` (2123 passed, 10 skipped); portal `npm test` and `npm run test:db` against a fresh Postgres; `npx tsc --noEmit`; `ruff check .` (0.15.20); `mypy` (1.14.1); `agentsmith conformance --contract 1|2|3` and `--port record --sender`; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `single-source-of-truth`, `pin-unremovable-duplicates`, `validate-on-the-receiving-side`, `test-the-contract`, `test-that-cannot-fail`, `failure-is-not-a-result`, `docs-match-behaviour`.

KG query: kg:104706756974
