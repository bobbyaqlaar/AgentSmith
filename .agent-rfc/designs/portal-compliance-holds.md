---
status: active
scope:
  - portal/lib/complianceState.ts
  - portal/lib/signInPolicy.ts
  - portal/lib/hitl.ts
  - portal/lib/submitOnce.ts
  - portal/components/StopControl.tsx
  - portal/components/HitlDecision.tsx
  - portal/app/ops/apps/[id]/page.tsx
  - portal/package.json
  - portal/test/**
  - scripts/compliance_port.py
  - scripts/test/test_compliance_port.py
  - agentsmith/runtime_server.py
  - agentsmith/test/test_compliance_runtime.py
---
# The portal's half of the `dubai-gov` profile holds

From the 4.1.0 release review: R15 (the checklist), R17, R21 (the queue), R23, R27, R28, R29 (the comparison, and the sidecar's sibling), R30. The Python half is `.agent-rfc/designs/compliance-profile-holds.md`.

## Problem

- **R15** The checklist read a signature with no `expires_at` as signed for ever.
- **R17** At 10,000 tracked names the failure map was cleared, unlocking every locked account.
- **R21** A timeout hid every later request for the same gate, so a gate asked again never reached the queue.
- **R23** `signInPolicy.test.ts`, `complianceState.test.ts` and `opsContract.test.ts` were in no npm script, so CI never ran them, yet `release:` rows cited one as "tested in AgentSmith's own CI". `release:` passed on any file that existed, including a route file (`OB-AUDIT-COVERAGE`). Nothing tested `hitl.ts`.
- **R27** `npm run lint` called `next lint`, which Next.js 16 removed.
- **R28** Stop and Resume could be sent twice, a failed fetch showed nothing, and a stop or a rejection fired on one click.
- **R29** `mayDecide` compared an email with free text, so a name never matched and a person could approve their own request.
- **R30** The manual's environment block still exported the deprecated shared token, and a maintenance snippet imported a framework-only script.

## Approach

- **Expiry.** `expiresAt(record, recurrence_days)` mirrors the port's `expires`: the earlier of `attested_at + recurrence_days` and `expires_at`. A signature dated more than five minutes ahead is not counted.
- **Lockout.** At the cap, expired entries go first, then the oldest unlocked ones. A locked entry is never evicted; if every entry is locked, a new name is not tracked rather than a lock dropped.
- **Queue.** `PENDING` hides a request only for a timeout with a higher `record_id`. It is exported so a test can hold the condition; the database test of the query stays with `test:db`.
- **Tests that run.** The three files join `npm test`, with three new ones (`hitl`, `submitOnce`, `scripts`). `scripts.test.ts` fails when a `test/*.test.ts` is in neither script. The port's `release:` passes only on a test CI runs: `test_*.py` under the two pytest folders, or a portal test one of the two scripts names. `OB-AUDIT-COVERAGE` cites a route file, so in AgentSmith's own evidence it now fails, which is the truth: no test proves every sign-in and human action is audited. Writing that test is listed as open in the backlog rather than rushed here.
- **Lint.** The `lint` script is removed. Adding ESLint means new dependencies and a config; the portal's CI already runs `tsc`. Listed as open.
- **Controls.** `lib/submitOnce.ts` (pure, tested) runs a send once, asks for confirmation first where given, and turns a thrown error into a message. `StopControl` takes `stopped` from the page and shows only the action that applies, confirms a stop, and shows "Stopping…" while busy. `HitlDecision` confirms a rejection through the same helper.
- **Requester.** `mayDecide` compares trimmed, lower-cased values, and a requester that is not an email means nobody may decide. The sidecar refuses a `requested_by` that is not an email with a 400, as the workflow path now does.
- **Manual.** The shared-token export is commented out, as `portal/.env.example` has it; the pruning snippet becomes `agentsmith gate kg build`.

## Pillars

- P1 applies — the review's findings are the requirement; `.agent-rfc/designs/portal-compliance-holds.md` is the plan.
- P2 applies — `portal/lib/submitOnce.ts` is one helper for both controls; no new dependency.
- P3 n/a — no span changes; the portal's tracing is untouched.
- P4 applies — `portal/test/scripts.test.ts` makes a test that no script runs fail CI; each finding has a test that fails on `origin/main`.
- P7 n/a — no model changes.
- P8 n/a — no telemetry.
- P9 applies — `portal/lib/hitl.ts` keeps a gate asked again in front of the reviewers.
- P10 n/a — no routing.
- P11 n/a — no untrusted content is newly read.
- P12 n/a — no secrets; the manual stops telling a tenant to set a deprecated one.
- P13 applies — `scripts/compliance_port.py` stops counting a file as evidence because it exists.
- P14 applies — `portal/package.json` changes, and `portal/test/scripts.test.ts` holds it to the test folder.
- P15 applies — `portal/lib/complianceState.ts` reads a requester it cannot compare as "nobody may decide", not "anyone may".
- P16 applies — `CHANGELOG.md` names each change; the stop control's new prop is passed by its only caller.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — `recurrence_days` in the checklist (R15).
- `guards-must-be-able-to-fail` — the lockout under pressure (R17).
- `out-of-order-and-repeated` — a gate asked again (R21).
- `implemented-not-invoked`, `gate-integrity` — tests CI runs, and evidence that is one (R23).
- `run-the-gates-ci-lists` — a script that cannot run is removed (R27).
- `no-double-submit`, `irreversible-needs-confirmation`, `failure-is-not-a-result` — the controls (R28).
- `validate-on-the-receiving-side` — the requester (R29).
- `docs-match-behaviour` — the manual (R30).
