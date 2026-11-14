---
status: active
scope:
  - agentsmith/vector_store.py
  - agentsmith/compliance.py
  - agentsmith/cli.py
  - agentsmith/test/test_compliance_runtime.py
  - portal/lib/hitl.ts
  - portal/components/StopControl.tsx
  - portal/app/ops/apps/[id]/page.tsx
  - portal/test/hitl.test.ts
---
# Each tenant has its own document ids, and the stop control shows the app's own state

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R17 and P2-R19, two minors the
owner asked for before the release. Follows `.agent-rfc/designs/compliance-profile-holds.md` (R25) and
`.agent-rfc/designs/portal-compliance-holds.md` (R28).

## Problem

- **P2-R17.** On the profile, `agentsmith_embeddings` is still keyed by `id` alone, shared by every tenant. R25 stopped
  one tenant's write from taking another's row by refusing it with "document id … belongs to another tenant", which
  (a) tells tenant B that tenant A holds that id, so B can probe any id; and (b) refuses every write to a row written
  before `tenant_id` existed (`NULL`), for every tenant, for ever, while reads on the profile never show such a row.
- **P2-R19.** The portal decides whether to offer "Stop app" or "Resume" from its own audit log. A stop or resume made
  at a terminal (`agentsmith ops stop`) never reaches that log, so the portal offers the wrong action. And
  `stopControl` posts to the app and then writes the audit line: if the post succeeds and the audit write fails, the
  operator reads "Not stopped" for an app that is stopped.

## Approach

- **P2-R17.**
  - On the profile, a document's stored id is `<tenant>:<id>`: each tenant writes and reads only its own id space,
    so another tenant's ids can neither be taken over nor detected. `query` returns the id the app wrote, without the
    prefix. Off the profile, nothing changes.
  - The R25 guard stays as a second line; its message no longer says whose the id is.
  - Rows written before the profile (`tenant_id` `NULL`, or this tenant's without the prefix) are moved into a
    tenant's id space by `agentsmith ops vector-claim` (a dry run unless `--apply`, which a person confirms at a terminal, as a purge). The move and a
    `vector_claim` record commit together (`_recorded_change`), because it changes who owns data. An id the tenant
    already holds is skipped and counted, never overwritten.
- **P2-R19.**
  - The stop state comes from the app: the newest `stop_control` record the app forwarded for the whole app (scope
    `*`), from `compliance_records`, which the app writes for a stop from the portal and from a terminal alike.
  - A stop or resume sent from the portal and newer than that record shows as "sent, waiting for the app to record
    it", so the page never claims a state the app has not recorded.
  - `stopControl` writes its audit line and posts to the app in one transaction, as `decideGate` does: if the app
    refuses, nothing is audited, and the operator's error is the app's answer.

## Pillars

- P1 applies — P2-R17 and P2-R19 are the requirement; `.agent-rfc/designs/vector-ids-per-tenant-and-stop-state.md` is the plan.
- P2 applies — `agentsmith/vector_store.py` and `portal/lib/hitl.ts` change in place; `agentsmith/cli.py` gains one subcommand; no dependency.
- P3 n/a — no spans or evaluations change.
- P4 applies — `agentsmith/test/test_compliance_runtime.py` and `portal/test/hitl.test.ts`; hand mutants after.
- P7 n/a — no model.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 applies — `agentsmith/vector_store.py`: one tenant learns nothing of another's documents, not even that an id exists.
- P12 n/a — no secrets.
- P13 applies — `agentsmith/compliance.py`: moving data into a tenant is a recorded change, or it does not happen.
- P14 n/a — no fixture or baseline.
- P15 applies — `portal/lib/hitl.ts`: "stopped", "running" and "sent, not yet recorded" are three states, not two.
- P16 applies — `agentsmith/cli.py`: `ops vector-claim` is a dry run by default and skips ids the tenant already holds; `CHANGELOG.md` says to run it once after enabling the profile on a store that already holds documents.

## Deviations

none

## Dependencies

none

## Levers

- `consistent-auth-gates` — reads and writes are both scoped to the tenant's id space (P2-R17).
- `denied-vs-missing` — a refusal no longer says whose the id is.
- `provenance-and-precedence` — the app's record is the stop state; the portal's own action is only "sent" (P2-R19).
- `failure-is-not-a-result` — a failed post is not audited as done.
- `test-that-cannot-fail` — hand mutants.
