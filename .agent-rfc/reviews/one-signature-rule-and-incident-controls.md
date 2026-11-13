# Review: one-signature-rule-and-incident-controls

Each fix has tests that fail without it. P2-R20: `fixtures/compliance/signature_cases.json` (eight cases written from
the rule, not from either implementation), read by `scripts/test/test_compliance_port.py` and by
`portal/test/complianceState.test.ts`; the portal failed the review's own case (an older live signature hidden by a
newer short-lived one). P2-R21: `portal/test/incidentsDb.test.ts` against Postgres, in `npm run test:db`: a second
close and a close through another app's id changed nothing and were audited as closes.

## Pass 1 — findings: 1

Against `docs/review-levers.md`, by hand mutants (seven).

1. **The route's 409 has no test of its own.** The incidents route reads the session through Next's request context,
   which the portal's plain Node tests cannot provide (the routes they do test authenticate by bearer token). The
   decision it maps (`closeIncident` returning false) is tested against the database, and the route adds two lines
   over it. Stated here rather than worked around with a mock of Next's headers.

## Pass 2 — findings: 0

- The mutants: the portal judging only the newest signature; an expired row showing nothing; the catalogue period
  ignored; the port judging only the newest (the shared cases kill it from the Python side too); a close audited
  whether or not it closed anything; the tenant ignored in the close; a closed incident closed again. All killed.
- Portal `npm test` and `npm run test:db` (103 ok, including the new file) against Postgres 16 with the CI job's
  environment: exit 0. `tsc`: clean. `scripts/test/test_compliance_port.py`, `test_compliance_checks.py`,
  `test_gate_steps.py`: 159 passed. ruff: clean. `scripts/test` checks that every portal test file is in a script
  (`scripts.test.ts`), and the new one is.
- Siblings: `IncidentForm`, `IncidentClose`, `StopControl` and `HitlDecision` now all write through `submitOnce`;
  `AttestForm` already had a busy state and a `catch`. The other portal client components that write were read: none
  left without one.
- The portal keeps its own copy of the rule (TypeScript cannot call the port); the shared case file is the pin
  `pin-unremovable-duplicates` asks for.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one rule, two implementations pinned by one case file; one `submitOnce` for every write control; incident writes moved to `portal/lib/incidents.ts`.
Group 2 · Quality / safety — [x] checked — a close is audited only when it closed something; a failed request is shown.
Group 3 · Architecture / hygiene — [x] checked — the route keeps its validation; the library holds the writes.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] checked — busy labels, an error line, and a confirmation before an irreversible close.
Group 6 · Signal integrity — [x] checked — the checklist and the check cannot disagree on the same signatures.
Group 7 · Auth & session integrity — [x] checked — a close through another app's id changes nothing and audits nothing.

Tests added: eight shared cases, read by both suites; two database tests in `portal/test/incidentsDb.test.ts`.
Mutation-checked: yes, by hand; seven mutants, all killed.
Fixtures re-pinned: `fixtures/compliance/signature_cases.json` (new); `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; `npm test`; `npm run test:db`; `tsc`; ruff; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `one-verdict`, `pin-unremovable-duplicates`, `no-double-submit`, `failure-is-not-a-result`, `irreversible-needs-confirmation`, `grep-for-siblings`, `test-that-cannot-fail`

KG query: kg:9d10ce3b0369
