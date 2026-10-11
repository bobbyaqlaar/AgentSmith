# The Ops contract, version 1

What a running application tells its **portal**, and what the portal sends back. An application
sends run status, dead letters and its declared settings; the portal sends a person's fix to a dead
letter back to the application's replay webhook, signed. A tenant runs nothing of the portal's:
which portal it reports to, and the credentials it holds, are its own configuration. AgentSmith's
runtime and portal are one sender and one receiver; this directory is what another platform
implements instead, and the suite that proves it did.

## Out: the Ops ingest

One JSON object, `message.schema.json`, per `POST` to the receiver's **Ops ingest address**, with
`Authorization: Bearer <token>` — an **Ops token** the receiver issued to the application. **The token
alone decides whose data a message is.** No message names a tenant, and a key that tries to is
dropped like any other key the receiver does not read.

| `kind` | Carries | Receiver keeps |
|---|---|---|
| `run` | `run_id`, `status` (`running` \| `success` \| `degraded` \| `failed`); optional `workflow_id`, `trace_id` (W3C, 32 hex, not all zero), `error_summary`, `input_tokens`, `output_tokens`, `cost_usd`, `framework_version` | one row per run, the newest status winning — except that a late `running` never un-finishes a finished run. Usage is absent, never zero, when it was not reported |
| `dead_letter` | `task_id`, `error`, `payload` (any JSON, `null` included); optional `reason` (a category: `validation_error`, `tool_call_error`, `hitl_timeout`, `hitl_rejected` and `infra_error` are named; a receiver shows one it does not know as it is), `workflow_id`, `gate_id` | one entry per `task_id`, the first winning |
| `settings` | optional `budget_cap_usd`, `replay_webhook_url` (`https`) | the newest of each field a message carries; a field it leaves out keeps what is stored |

Every message carries `schema: 1`. Limits are in the schema: 4,000 characters in any text, 200 in an
id, **1,000,000 bytes** in a body.

**A settings message never carries a secret.** The replay key is the receiver's to issue (below); a
settings message naming `replay_webhook_secret` is refused — the one key a receiver refuses rather
than drops.

### The transport

As `contract/record/v1`: `https`, or `http` to a loopback address only; **a redirect is never
followed**, and is a failure — a client that follows one copies the token to wherever it points.

### The answers

| Status | Means |
|---|---|
| `200` `{"stored": n}` | stored — `0` for a dead letter this application sent before: resending is safe |
| `400` | the message is not one this receiver reads — refused whole, nothing stored |
| `401` | no token, or one the receiver did not issue as an Ops token |
| `409` | the `run_id` or `task_id` belongs to another application — never written over |
| `413` | the body is larger than the receiver reads |
| `5xx`, or no answer | the receiver is unwell |

**Failure is open, and said.** A worker never fails the work it reports on: whatever the answer, it
carries on and warns once per process. A sender run as a CI step **fails** on `400`, `401` and a
redirect — configuration, not an outage — **warns** on `5xx`, and, with no receiver configured, sends
nothing and says so.

## In: the replay request

When a person fixes a dead letter, the receiver `POST`s `replay.schema.json` — `{"schema": 1,
"taskId", "payload"}` — to the `replay_webhook_url` the application's settings declared, with:

```
X-Replay-Timestamp: <unix seconds>
X-Replay-Signature-V2: sha256=<hex HMAC-SHA256, under the replay key, over "<timestamp>.<body>">
```

The **replay key** is issued by the receiver to the application — shown once, for the application to
hold; the receiver keeps it to sign. The application refuses (`401`) a request whose signature does
not verify or whose timestamp is more than **300 seconds** from its clock; answers `2xx` when it
accepted the fix, `409` when the entry was no longer pending, and `404` when it has no such entry. The
receiver **never follows a redirect** from the webhook: the signed fix goes to the declared address or
nowhere.

## Conformance

```bash
agentsmith conformance --port ops --sender "<command>"
agentsmith conformance --port ops --receiver <ingest address>     # token in GOVERNANCE_OPS_TOKEN
agentsmith conformance --port ops --replay <webhook address>       # key in GOVERNANCE_REPLAY_KEY
```

**A sender** is run in a repository whose `tenant.yaml` declares a budget cap, a replay webhook and —
where a careless sender would find it — a replay secret, against a loopback receiver at
`OPS_PORTAL_URL` with its token in `OPS_PORTAL_TOKEN` (`--url-env`, `--token-env` name others). Every
message must satisfy the schema, carry the token and not the secret; a `302` to a second address must
not be followed; a `401` must fail the command and a `503` must not; with no receiver configured, it
must send nothing and say so.

**A receiver** is sent `cases.json` — each case one of `fixture.json`'s messages with one thing
changed, its ids made unique to the run — and refused messages of its own: no token, an unknown
token, a body over the limit. Only the status is matched; a receiver words its own refusals. Valid
cases store data under the token's application, so point the run at a test portal.

**A replay webhook** is sent `fixture.json`'s replay request signed correctly, signed ten minutes ago,
signed under another key, and unsigned. The first must not be refused for its signature; the others
must be refused with `401`.

## What is not in version 1

The application's own history log, and human feedback flowing into its evaluation data, are not Ops
records. An in-app status feed for end users is the portal's own surface. A dead-letter table the
portal and a worker share is not part of the contract; the ingest makes sharing unnecessary.
