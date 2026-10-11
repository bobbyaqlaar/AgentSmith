---
status: active
scope:
  - contract/ops/v1/**
  - runtime/ops_contract.py
  - runtime/llm_gateway.py
  - runtime/dead_letter.py
  - runtime/worker.py
  - runtime/cli.py
  - runtime/conformance.py
  - runtime/machine/ops.py
  - runtime/replay_webhook_server.py
  - scripts/shadow-eval.py
  - runtime/test/**
  - scripts/verify_system.py
  - scripts/sync-portal-history.py
  - scripts/_shared.py
  - scripts/test/**
  - scripts/mutation_check.py
  - portal/**
  - workflow-templates/**
  - .github/workflows/self-test.yml
  - .agenticframework/process-gates.json
---
# C8 — The Ops contract: what a running tenant tells its portal, and what the portal sends back

Slice C8 of `.agent-rfc/designs/governance-contracts.md`. Ops records are a **wire port**, like the
dev record (C3) and telemetry (C5): the tenant sends data and runs nothing of the provider's. Today
the wire exists in four unpublished shapes, one of them a shared database, all of them trusting a
tenant id the caller writes.

## Problem

Measured on 2026-10-10:

- **One token for every tenant, and the tenant named in the body.** `/api/runs/ingest` (run status,
  from `runtime/llm_gateway.py`, twice per model call) and `/api/sync/history` both check one shared
  `OPS_PORTAL_SYNC_TOKEN` and then write whichever `tenantId` the body names: any holder can write
  any tenant's runs, budget cap and replay webhook. The dev record (C3) already uses a token per
  application that alone decides the tenant (`app_ingest_tokens`).
- **Dead letters reach the portal through its database.** `runtime/dead_letter.py` inserts into
  `dlq_entries` with the worker's `DATABASE_URL`; the portal's HITL queue reads the same table. A
  tenant can feed the queue only by sharing the portal's Postgres.
- **The replay key is meant to be committed.** The portal signs a human's fix with a per-tenant secret
  it learns from `sync-portal-history.py`, which reads `hitl.replay_webhook_secret` from
  `tenant.yaml` — a committed file (KYC's carries the commented template) — and sends it over the
  shared-token channel. The worker already verifies with `REPLAY_WEBHOOK_SECRET` from its environment.
- **The replay request follows redirects.** `portal/lib/dlq.ts` `fetch`es the tenant's webhook with
  the default `redirect: "follow"`: a 3xx sends the signed fix — replayable for five minutes —
  wherever it points.
- **The CD history sync is hollow.** `.agent-history.log` is gitignored in AgentSmith and KYC, so a
  CD checkout has none; `sync-portal-history.py` sends only the budget cap and the replay webhook.
  OTS's CD and the workflow templates run it, and `sync-ui-feedback.py` (Phoenix annotations into
  the golden dataset), by path.
- **No published shape**: the run-status body is documented in a route comment, the dead letter in a
  DDL, the replay request in a function.

**The owner's decisions (2026-10-10):** a separate per-application Ops token; dead letters over HTTP;
the portal issues the replay signing key; both sync scripts retired from tenant CD, and the Phoenix
promotion logged as an evals-data feature.

## Approach

### `contract/ops/v1/` — a wire port, both directions

**Out: the tenant's Ops ingest.** One address; one JSON message per `POST`; `Authorization: Bearer
<token>` — an **Ops token** the receiver issued to the application, which alone decides whose data
it is (a message names no tenant). Transport as `contract/record/v1`: `https`, or `http` to loopback
only; **a redirect is never followed** and is a failure; limits stated in the schema.

`message.schema.json`: `{schema: 1, kind, …}` —

| `kind` | Carries | Receiver keeps |
|---|---|---|
| `run` | `run_id`, `status` (`running` \| `success` \| `degraded` \| `failed`), optional `workflow_id`, `trace_id`, `error_summary`, `input_tokens`, `output_tokens`, `cost_usd`, `framework_version` | one row per run, newest status winning, a late `running` never un-finishing a run |
| `dead_letter` | `task_id`, `error`, `payload`, optional `reason` (`validation_error` \| `tool_call_error` \| `hitl_timeout` \| `hitl_rejected` \| `infra_error`), `workflow_id`, `gate_id` | one entry per `task_id`, the first winning |
| `settings` | optional `budget_cap_usd`, `replay_webhook_url` (`https`) — **never a secret** | the newest |

Answers: `200` stored; `400` refused whole (a shape, a value, a limit); `401` no or unknown token;
`413` too large; `5xx` or none — unwell. **Failure is open, and said** (the umbrella's rule for Ops
records): a worker never fails a request over its report — it warns once per process and carries on;
a CI step that sends `settings` fails on `400`/`401` (configuration, as the record contract), warns
on `5xx`, and says plainly when no receiver is configured.

**In: the replay request.** When a human fixes a dead letter, the receiver `POST`s `replay.schema.json`
— `{schema: 1, task_id, payload}` — to the `replay_webhook_url` the tenant's settings declared, with
`X-Replay-Timestamp` and `X-Replay-Signature-V2: sha256=<hex HMAC-SHA256 over "<timestamp>.<body>">`
under the application's **replay key**. The tenant refuses a signature outside 300 seconds, answers
`2xx` when it accepted the fix and `409` when the entry was no longer pending. The receiver issues
the replay key — shown once, kept to sign — and **never follows a redirect** from the webhook.

### AgentSmith's portal as the receiver

- **Ops tokens**: `app_ingest_tokens` gains `scope` (`dev` | `ops`, default `dev` — every existing
  token stays a dev token); the dev ingest accepts only `dev`, the Ops ingest only `ops`; rotation and
  revocation are per scope. Administration › Apps › an app: an **Ops token** panel beside the ingest
  token one (the same component), and a **Replay signing key** panel — issue or rotate, shown once,
  audited.
- **`POST /api/ops/ingest`** (`lib/opsIngest.ts`): validates each kind whole, then writes through the
  existing stores — `upsertAgentRun`, `dlq_entries` (`ON CONFLICT DO NOTHING`), the tenant's budget
  cap and replay URL. A span per request, as the other ingests.
- **The deprecated routes stay, narrowed.** `/api/runs/ingest` and `/api/sync/history` keep answering
  the shared token for runtimes already deployed (an operator turns them off by unsetting
  `OPS_PORTAL_SYNC_TOKEN`); `/api/sync/history` **stops storing a replay secret** — the key is the
  portal's to issue — and keeps the URL and the budget cap.
- **Replay** stops following redirects (`redirect: "manual"`; a 3xx is a failure that says so) and
  signs with the issued key. The legacy body-only signature is still sent, as today, for receivers
  older than v2; the contract names only v2.

### AgentSmith's runtime as a sender

- **`runtime/ops_contract.py`**: the message models (Pydantic V2; the published schemas are generated
  from them), and `send(kind, body)` — `OPS_PORTAL_URL` + `/api/ops/ingest` with `OPS_PORTAL_TOKEN`,
  bounded timeouts, no redirects, fail-open with one warning per process.
- **Run status** goes by `send("run", …)` when `OPS_PORTAL_TOKEN` is set; with only the shared token,
  the deprecated route as today, warning once that it is deprecated.
- **Dead letters** are sent after the worker's own store has them (`DeadLetterQueue.enqueue`); the
  worker keeps its own store — replay claims its own row, as today.
- **Settings** are sent by the worker at start-up (`runtime/worker.py`) from `tenant.yaml` —
  `budget.monthly_usd_cap` (the key the gateway enforces), else `gateway.budget_cap_usd`;
  `hitl.replay_webhook_url`. A `hitl.replay_webhook_secret` there is never sent: the worker warns
  that it belongs in `REPLAY_WEBHOOK_SECRET`, issued by the portal. `agentsmith ops settings` sends the
  same message from a CI step, for a tenant without the worker.

### Retired

- **`scripts/sync-portal-history.py`** is deleted: its only callers — the CD templates, `agentsmith
  check`, `verify_system.py --check-history-sync` — go with it; the self-test's live-portal step runs
  the Ops receiver conformance instead, with an Ops token it seeds.
- **`sync-ui-feedback.py` leaves tenant CD** (`workflow-templates/cd-production.yml`); it stays the
  first half of `agentsmith evals` on a developer's machine. Promoting human feedback into a tenant's
  own dataset is logged on the backlog as an evals-data feature.
- The CD templates send nothing in their place: the deployed worker reports its own settings.

### Amended while building (2026-10-11)

- **A dead letter's `reason` is an open category.** `runtime/dead_letter.py` calls its five reasons
  "not exhaustive" and the portal shows an unknown one as it is; a closed list would have refused a
  tenant's own category whole. The five are named, not required.
- **A run's `run_id` and a dead letter's `task_id` are unique across apps**, and the portal's
  `agent_runs` upsert ignored the tenant: per-app tokens alone would still have let one app overwrite
  another's run. The upsert is guarded by tenant on both routes; an id another app holds is `409`.
- **The portal creates `dlq_entries` when the first dead letter arrives by the contract**, with the
  runtime's DDL (pinned by a test), so "not wired" keeps meaning no dead letter has reached it by
  either route.
- **A settings message carrying `replay_webhook_secret` is refused**, not dropped — the one key a
  receiver refuses; the schema says so.
- **The replay request keeps `taskId`** — the name deployed receivers read — and gains `schema: 1`.
- **`cd-production.yml` drops to `contents: read`**: the fixture PR step left with the Phoenix sync,
  and nothing else in the job writes.
- **The record contract's conformance flags are reused** for the Ops sender and receiver; the replay
  check adds `--replay`.

### Conformance

`agentsmith conformance --port ops --sender "<command>"` runs the command with `OPS_PORTAL_URL` and
`OPS_PORTAL_TOKEN` pointing at a loopback receiver and judges every message: the schema, the token,
no redirect followed (one answer is a `302` to a second address that must see nothing), a `401`
and a `503` survived. `--receiver <ingest address>` (token in `GOVERNANCE_OPS_TOKEN`) sends
`cases.json` — each case one message changed — and matches only the status. `--replay <url>` (key in
`GOVERNANCE_REPLAY_KEY`) sends a correctly signed replay and the same replay stale and mis-signed, and
expects `2xx`, then refusals. AgentSmith's sender (`agentsmith ops settings`), its portal (self-test,
live) and its `replay_webhook_server.py` are each scored by them.

### Tenant steps — after the release that carries it

- **OTS**: its CD drops the history and the UI-feedback steps (both run its vendored scripts by path);
  it has no worker, so it sends `settings` from CD with `agentsmith ops settings` through the setup
  step it already has — a step that says it sent nothing while no Ops address is configured.
- **KYC Sentinel**: `tenant.yaml`'s HITL comment stops telling an operator to put the replay secret
  there; its worker reports by the contract once its deployment holds an Ops token (KYC's deployment
  is suspended; nothing to send today).

**Deliberately not done:** moving the portal's DLQ table out of a database a tenant may still share
(the HTTP path makes sharing unnecessary; removing the option is C9's or later); the in-app widget's
status feed (an end-user read, not an Ops record); OTS's own telemetry.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C8; the owner's four decisions are recorded in Problem; this design precedes the code.
- P2 applies — `portal/lib/opsIngest.ts` writes through the existing stores (`runStatus`, `dlq`, `tenants`); the Ops token reuses `app_ingest_tokens` and `IngestTokenPanel` with a scope; `runtime/ops_contract.py` is the one sender. No dependency added.
- P3 applies — `portal/app/api/ops/ingest/route.ts` opens a `portalSpan` per message, with the kind; the runtime's send carries `traceparent`, as the run-status post does today.
- P4 applies — `runtime/conformance.py`'s Ops suite for a sender, a receiver and a replay webhook; portal tests for each kind's validation and token scope; runtime tests for each sender; mutations: a dev token accepted at the Ops ingest, a body tenant beating the token, a redirect followed by the sender and by the replay, a secret sent in settings, a late `running` un-finishing a run.
- P7 applies — `runtime/ops_contract.py`: the messages are Pydantic V2 models with generated schemas; the portal validates in TypeScript at the receiving side.
- P8 applies — `contract/ops/v1/protocol.md` publishes the run-status wire `CHANGELOG.md`'s Wire Contract table describes, with its version field.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — `portal/lib/opsIngest.ts` treats every body as untrusted: validated whole, capped, a payload stored as JSON and never interpreted.
- P12 applies — `portal/lib/apps.ts` issues the replay key and the Ops token, shown once, the token hashed; no secret travels in a message, and `tenant.yaml` stops being the place a secret is asked for.
- P13 applies — `portal/lib/ingestTokens.ts` scopes tokens so a dev token cannot write Ops data nor an Ops token dev records; the token alone decides the tenant.
- P14 applies — `contract/ops/v1/fixture.json` carries one valid message of each kind; cases change one thing each.
- P15 applies — `runtime/ops_contract.py` says when nothing was sent, or why, rather than succeeding silently; `400` and `401` from CI are failures, `5xx` a warning.
- P16 applies — `portal/app/api/runs/ingest/route.ts` and `portal/app/api/sync/history/route.ts` stay, narrowed, until an operator unsets the shared token, so deployed runtimes keep reporting while tenants move.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the token decides the tenant; a body naming one decides nothing.
- `two-owners-two-cadences` — runtimes already deployed keep the deprecated routes until the portal's operator turns them off.
- `single-source-of-truth` — one ingest, written through the stores that already exist; schemas generated from models.
- `test-the-contract` — sender, receiver and replay webhook each conformance-checked; a redirect is tested both ways.
- `implemented-not-invoked` — the hollow history sync goes rather than being contracted.
- `channel-precedence` — one credential per channel: the CI token, the Ops token, the replay key; none can stand in for another.
