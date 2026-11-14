---
status: active
scope:
  - scripts/compliance_port.py
  - scripts/test/test_compliance_port.py
  - fixtures/compliance/signature_cases.json
  - portal/lib/complianceState.ts
  - portal/test/complianceState.test.ts
  - portal/lib/incidents.ts
  - portal/app/api/incidents/route.ts
  - portal/components/IncidentForm.tsx
  - portal/components/IncidentClose.tsx
  - portal/test/incidentsDb.test.ts
  - portal/package.json
---
# The port and the portal judge a signature the same way, and the incident controls send once

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R20 and P2-R21, two minors the
owner asked for before the release. Follows `.agent-rfc/designs/portal-compliance-holds.md` (R15, R28).

## Problem

- **P2-R20.** For a recurring obligation the port (`scripts/compliance_port.py`, `latest_valid`) takes the newest
  signature that is still live; the portal (`portal/lib/complianceState.ts`, `checklist`) takes the newest signature
  and judges only it. Signed on 1 January with no expiry and again on 1 February with `expires_at` 2 February, on
  1 March the port says signed and the portal says expired. `expiresAt` "mirrors" `expires`, and the choice of record
  around it does not.
- **P2-R21.** R28 fixed the stop control and the decision control. Beside them, `IncidentForm` has no busy state (a
  double click opens two incidents) and no `catch` (a failed request shows nothing); `IncidentClose` has no busy
  state, says nothing when its request fails, and closes with no confirmation; and the route writes an audit line for a
  close even when the `UPDATE … AND status = 'open'` changed nothing.

## Approach

- **P2-R20.** One rule, the port's: the newest signature that is neither dated in the future nor expired counts. The
  portal's `checklist` picks that record; with none live, the row is `expired` (showing the newest signature) or
  `missing`. `fixtures/compliance/signature_cases.json` holds cases (records, period, the moment judged, the record
  that counts, the portal's state), and both test suites read it, so neither side can drift alone.
- **P2-R21.**
  - `portal/lib/incidents.ts` holds open and close. Close returns whether it closed a row; the audit line is written
    only then, and the route answers 409 "already closed, or not this app's" otherwise.
  - Both controls go through `submitOnce`: one request at a time, a busy label, and the error shown when it fails.
    Closing asks first: an incident cannot be reopened.
  - `portal/test/incidentsDb.test.ts` runs against Postgres in `npm run test:db`.

## Pillars

- P1 applies — P2-R20 and P2-R21 are the requirement; `.agent-rfc/designs/one-signature-rule-and-incident-controls.md` is the plan.
- P2 applies — `portal/lib/complianceState.ts` changes in place; `portal/lib/incidents.ts` takes the route's two writes; no dependency.
- P3 n/a — no spans or evaluations.
- P4 applies — `scripts/test/test_compliance_port.py` and `portal/test/complianceState.test.ts` read one case file; `portal/test/incidentsDb.test.ts` runs in `npm run test:db`; hand mutants after.
- P7 n/a — no model.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 n/a — no untrusted content.
- P12 n/a — no secrets.
- P13 applies — `fixtures/compliance/signature_cases.json` pins the two implementations to one rule.
- P14 applies — `fixtures/compliance/signature_cases.json` is new, written from the rule, not from either implementation's output.
- P15 applies — `portal/app/api/incidents/route.ts`: a close that changed nothing is a 409, not an audited success.
- P16 applies — `portal/components/IncidentForm.tsx` and `portal/components/IncidentClose.tsx` say when a request failed, so the operator can try again.

## Deviations

none

## Dependencies

none

## Levers

- `one-verdict` — one rule for which signature counts (P2-R20).
- `pin-unremovable-duplicates` — the two implementations stay, so a shared case file pins them.
- `no-double-submit`, `failure-is-not-a-result`, `irreversible-needs-confirmation` — the incident controls (P2-R21).
- `grep-for-siblings` — the controls R28 did not reach.
- `test-that-cannot-fail` — hand mutants.
