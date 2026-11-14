---
status: active
scope:
  - agentsmith/compliance.py
  - agentsmith/workflows/base_workflow.py
  - agentsmith/test/test_compliance_runtime.py
  - portal/lib/hitl.ts
  - portal/test/hitl.test.ts
---
# A human decision names the request it answers, and a resume is written with its record

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R14, the store-path sibling of
P2-R13, and P2-R15. Follows `.agent-rfc/designs/review-pass2-majors.md` and
`.agent-rfc/designs/compliance-profile-holds.md`.

## Problem

- **P2-R14.** A decision says which input it approved (`payload_sha256`) but not which request. On the store path
  `find_decision` takes the latest decision and the latest request for a gate and compares their digests, so a late
  decision on request 1 answers request 2 when both showed the same input. The Temporal path drops decisions given
  before the gate asked, but still cannot tell two requests with one input apart.
- **P2-R15.** `clear_stop` writes the `resume` record, commits it, and then deletes the stop in a second transaction.
  When the delete fails, the chain says "resumed" and the app is still stopped. `_recorded_change` exists for exactly
  this and `set_stop` uses it.

## Approach

- **P2-R14.** `HumanDecision` gains `request_record_id`, required: the record id of the `hitl_pending` record the
  reviewer was shown. The portal already holds it (`decideGate`'s `recordId`) and sends it. On the store path,
  `find_decision` accepts only a decision naming the latest request's record id, with that request's digest. On the
  Temporal path the workflow waits for a decision naming the record id the pending activity returned, as well as its
  digest. Required, not optional, because the profile ships for the first time in 4.1.0: no released runtime or portal
  speaks the old shape, and an optional field would leave the old ambiguity as the fallback.
- **P2-R15.** `clear_stop` uses `_recorded_change`: the delete and the `resume` record commit together, or neither.

## Pillars

- P1 applies — P2-R14 and P2-R15 are the requirement; `.agent-rfc/designs/decision-names-its-request.md` is the plan.
- P2 applies — `agentsmith/compliance.py` (`HumanDecision`, `find_decision`, `clear_stop`), `agentsmith/workflows/base_workflow.py` and `portal/lib/hitl.ts` change in place; no dependency.
- P3 n/a — no spans or evaluations.
- P4 applies — `agentsmith/test/test_compliance_runtime.py` (with a database where it needs one) and `portal/test/hitl.test.ts`; hand mutants after.
- P7 n/a — no model.
- P8 n/a — no telemetry.
- P9 applies — `agentsmith/workflows/base_workflow.py`: the gate waits for a decision about its own request.
- P10 n/a — no routing.
- P11 n/a — no untrusted content.
- P12 n/a — no secrets.
- P13 applies — `agentsmith/compliance.py`: a decision that does not name the request it answers is not an answer, on both paths.
- P14 n/a — no fixture or baseline changes.
- P15 applies — `agentsmith/compliance.py`: a `resume` record means the app was resumed.
- P16 applies — `CHANGELOG.md` names the new required field; `contract/compliance/v1/protocol.md` says what a decision carries.

## Deviations

none

## Dependencies

none

## Levers

- `out-of-order-and-repeated` — two requests with one input, and a decision arriving late (P2-R14).
- `grep-for-siblings` — the store path beside the Temporal path; `clear_stop` beside `set_stop`.
- `merge-the-right-copy` — `_recorded_change` already does what `clear_stop` needs (P2-R15).
- `two-owners-two-cadences` — the portal and the runtime ship in the same release, and no released version speaks the old shape.
- `test-that-cannot-fail` — hand mutants, and database tests run against Postgres.
