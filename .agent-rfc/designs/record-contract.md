---
status: active
scope:
  - contract/record/v1/**
  - scripts/gate_models.py
  - scripts/process_gate.py
  - scripts/send_dev_record.py
  - runtime/conformance.py
  - runtime/cli.py
  - portal/lib/devIngest.ts
  - portal/test/**
  - portal/package.json
  - scripts/test/**
  - runtime/test/**
  - scripts/mutation_check.py
  - .agenticframework/process-gates.json
---
# C3 — The record contract: what a gate provider tells a portal

Slice C3 of `.agent-rfc/designs/governance-contracts.md`. Since C1 a tenant's CI sends nothing
itself: the gate provider answers `ci` and sends the record of what it decided to the portal. This
slice publishes that record and the way it travels as a contract — so a third-party gate provider
can feed AgentSmith's portal, AgentSmith's provider can feed another portal, and the two sides can
no longer drift apart in silence.

## Problem

The record works, and nothing defines it:

- **Two hand-written copies of one shape.** `scripts/process_gate.py` builds the record as plain
  dicts; `portal/lib/devIngest.ts` validates it field by field. What keeps them equal is one test
  that reads the TypeScript `DEV_RECORD_SCHEMA` number with a regex, and the verdict catalogue pinned
  separately. A renamed field, a new verdict or a changed limit on either side is caught only if
  someone thought to pin that one.
- **No Python model.** The provider writes whatever the dict holds; nothing checks it against the
  shape the portal will accept until the portal refuses it in someone's CI.
- **The transport is described only in code.** `scripts/send_dev_record.py` is where the rules live —
  POST with the app's bearer token, https except loopback, never follow a redirect (the token would
  follow it), at most 500 commits per request with the designs on the last part, refused (4xx) fails
  the run, unreachable or failing (5xx) warns — and the portal's limits are in `DEV_LIMITS`. A
  second sender or receiver would have to read both programs to learn them.

**What tenants hold here:** nothing, any more. Neither KYC Sentinel nor OTS sends a record, and since
C1 the gates workflow has no record step — verified. So this slice's proof is the contract's own
conformance on both ends, not a tenant deleting a file.

## Approach

### `contract/record/v1/`

- **`record.schema.json`** — the record, generated from a new Pydantic model, `DevRecord` (with
  `DevCommit`, `DevDesign`, `DevReview`), in `scripts/gate_models.py`: snake_case as the gate writes
  it, the verdict and pillar catalogues as enums, the per-field limits as `maxLength`/`maxItems`.
  `schema` is the constant `1`.
- **`protocol.md`** — the transport, as `send_dev_record.py` and the portal already behave:
  - `POST` the record as JSON to the receiver's ingest address, `Authorization: Bearer <token>`;
  - `https`, or `http` to a loopback address only; a redirect is **never followed** — the token would
    go with it — and is a failure;
  - at most **500 commits per request**: a longer range goes in parts, oldest first, and only the last
    part carries `designs` (the designs at the head);
  - responses: `200 {"stored": n}`; **4xx is a refusal** — the record or the token is wrong, and the
    sender fails its run, because nobody learns it from a green tick; **5xx or no answer** — the
    receiver is unwell, the sender warns and the next run sends again;
  - **resending is safe**: a receiver stores a commit once per app (`sha`), the newest record winning;
  - a receiver drops keys it does not know and refuses a body with any field outside the schema's
    limits, whole.
- **`fixture.json`** — a valid record; **`cases.json`** — bodies and the answer each must get: valid
  (`200`), a schema it does not read (`400`), an unknown verdict (`400`), more than 500 commits
  (`400`), an oversize body (`413`), no token (`401`), an unknown token (`401`).

### One shape, checked on both sides

- **The provider validates before it sends.** `ci --json` and the contract-2 `ci` answer build the
  record, then `DevRecord.model_validate` it: a record the contract would refuse never leaves the
  machine, and a gate change that breaks the shape fails the gate's own tests.
- **The portal is held to the published file.** `portal/test/devIngest.test.ts` reads
  `contract/record/v1/fixture.json` and `cases.json` and runs them through `parseDevIngest` and the
  handler; its `DEV_RECORD_SCHEMA`, `DEV_VERDICTS`, `PILLAR_KINDS` and `DEV_LIMITS` are checked against
  `record.schema.json` rather than against a regex of each other. The regex pin goes.

### Conformance, for a sender and for a receiver

`agentsmith conformance --port record` gains two modes:

- **`--sender "<gate command>"`** — builds the gate fixture, stands up a loopback receiver, points the
  provider at it, and runs `ci`: the body must validate against the schema, carry the bearer token,
  arrive in parts above 500 commits; a receiver that answers `302` must not be followed and must fail
  the answer; `401` must fail it; `503` must not.
- **`--receiver <ingest url>`** with the token in `GOVERNANCE_RECORD_TOKEN` — posts the cases and
  checks each status. It writes test records under that token's app, so it is meant for a test
  portal. AgentSmith's own portal is scored in its database test run, against a fresh Postgres.

### What does not change

The variables the AgentSmith provider reads — `AGENTSMITH_PORTAL_URL`,
`AGENTSMITH_PORTAL_INGEST_TOKEN` — are that provider's configuration, not part of the wire; another
provider names its own. No tenant secret is renamed and no declaration is added: the record is sent
by whichever gate provider the repository declares, to whichever receiver that provider is
configured for.

**Deliberately not done:** run history and HITL feedback between a tenant and the portal (C8, the
Ops records); a records port in `providers.json` (nothing would read it); renaming the ingest route.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C3; `.agent-rfc/designs/portal-phase1.md` is where the record was first designed; this design precedes the code.
- P2 applies — `scripts/send_dev_record.py` and `portal/lib/devIngest.ts` already implement every rule the protocol states; the contract writes them down once, and the schema is generated from a model rather than written by hand. `runtime/conformance.py` gains the port rather than a second runner. No dependency added.
- P3 applies — `scripts/process_gate.py` builds the record inside the `ci` span; validation adds no new path. The portal's ingest route is unchanged.
- P4 applies — `runtime/conformance.py`'s record sender and receiver suites, run against AgentSmith's provider and its portal; `portal/test/devIngest.test.ts` runs the contract's cases; `scripts/test/test_dev_record.py` asserts what the gate writes validates. Mutations: a field the provider drops, a verdict the portal stops accepting, a redirect followed, a 401 that passes.
- P7 applies — `scripts/gate_models.py`: the record becomes Pydantic models with the limits as constraints, the schema generated from them; the portal's types stay TypeScript, checked against the generated file.
- P8 n/a — no telemetry changes.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `portal/lib/devIngest.ts` treats the body as data from outside, validates every field and drops unknown keys; the contract states that as a receiver's duty, and the cases exercise it.
- P12 applies — `scripts/send_dev_record.py` sends the token only over https or to loopback and never across a redirect; the contract makes both a sender's duty, and the sender suite checks the redirect. The token is never in a case file or a report.
- P13 n/a — no gate check is added, removed or weakened; the gate's verdicts are unchanged, and a record that fails validation fails the run rather than being sent short.
- P14 applies — `scripts/test/test_dev_record.py`'s regex pin is replaced by a check of both sides against `contract/record/v1/record.schema.json`; existing portal fixtures are re-pinned to the contract's fixture where they duplicate it.
- P15 applies — `scripts/send_dev_record.py` already keeps refused, unwell and not configured apart; the contract names the three, and the sender suite asserts a `401` fails and a `503` does not.
- P16 applies — `portal/lib/devStore.ts` already stores each commit once per app with the newest record winning (`ON CONFLICT … DO UPDATE`); the protocol makes that every receiver's duty, so a run whose record was not stored is repaired by the next run, with no manual step.

## Deviations

none

## Dependencies

none

## Levers

- `single-source-of-truth` — one model, one generated schema; both the provider and the portal are checked against it.
- `pin-unremovable-duplicates` — the TypeScript validator cannot be generated away, so it is pinned to the published schema, not to the Python constant by regex.
- `validate-on-the-receiving-side` — the portal still validates every field; the contract makes it every receiver's duty.
- `test-the-contract` — conformance for a sender and for a receiver, both run against AgentSmith.
- `failure-is-not-a-result` — refused, unwell and not configured stay three answers.
- `docs-match-behaviour` — the protocol is written from what the code does, and the conformance runs keep it true.
