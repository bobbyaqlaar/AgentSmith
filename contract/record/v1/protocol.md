# The record contract, version 1

When a gate provider answers a CI run (gate contract 2's `ci` event), it can tell a **portal** what it
decided: about each commit of the range, and about the designs at its head. This contract is that
message and how it travels — so any gate provider can feed any portal that speaks it, and AgentSmith's
provider and portal are held to it like anyone else's.

The parties are a **sender** (a gate provider, in a tenant's CI) and a **receiver** (a portal). A
tenant holds no part of it: which receiver a sender uses, and the token it presents, are the sender's
own configuration.

## The message

One JSON object, `record.schema.json`, per request:

- `schema` — the constant `1`;
- `head` — the commit the range ends at;
- `commits` — what was decided about each commit: its verdict (`passed`, `failed`,
  `passed_with_notes`, `not_gated`, `before_adoption`), the errors and notes behind it, the commits it
  repairs, and the design and review it names — each resolved, or with the reason it could not be;
- `designs` — every design document as it stands at `head`, or absent: a receiver keeps the designs it
  has when a record carries none;
- `ci_run_url` — where the run can be read, if anywhere.

The schema's limits are the receiver's: at most **500 commits** in one request, 200 entries in any
list, 4,000 characters in any text, 1,000 in a subject, and **2,000,000 bytes** in a body.

## The transport

- **`POST`** the record as JSON to the receiver's ingest address, with
  `Authorization: Bearer <token>` — a token the receiver issued to the application the record is about.
- **`https`**, or `http` to a loopback address only. The token is never sent in the clear across a
  network.
- **A redirect is never followed**, and is a failure. A client that follows one copies the
  `Authorization` header onto the next request, and the token goes wherever the redirect points.
- **A range longer than 500 commits goes in parts**, oldest first, each a whole record. Only the last
  part carries `designs`, because only its `head` is the range's head.

## The answers

| Status | Means | The sender |
|---|---|---|
| `200` `{"stored": n}` | stored | carries on |
| `400` `{"error": …}` | the record is not one this receiver reads — a shape, a value, a limit | **fails its run**: nobody learns a wrong record from a green tick |
| `401` | no token, or one the receiver does not know | **fails its run**: a wrong token is configuration, not an outage |
| `413` | the body is larger than the receiver reads | **fails its run**, and should have sent parts |
| `5xx`, or no answer | the receiver is unwell | **warns** and carries on: the gate's verdict does not depend on the portal, and the next run sends again |

A sender that is not configured with a receiver at all says so and carries on — a repository without a
portal is not a failed build.

## What a receiver promises

- **It validates every field** of a body it did not write, and refuses the body **whole** on the first
  that fails — never storing half a record.
- **It drops keys it does not read.** A sender that adds a field breaks no receiver.
- **Resending is safe.** A commit is stored once per application, the newest record winning, so a run
  whose record was not stored is repaired by the next one, and a range sent twice changes nothing.

## Conformance

```bash
agentsmith conformance --port record --sender "<gate command>"
agentsmith conformance --port record --receiver <ingest address>     # token in GOVERNANCE_RECORD_TOKEN
```

**A sender** is run against the gate contract's fixture repository with a loopback receiver standing
in for a portal. What it sends must satisfy the schema and carry the token; a receiver answering
`302` must not be followed and must fail the answer; `401` must fail it; `503` must not.

**A receiver** is sent `cases.json` — each case `fixture.json`'s record with one thing changed — and
must answer each with its status. Only the status is matched: a receiver words its own refusals. The
run stores the valid record under the token's application, so point it at a test portal.

## What is not in version 1

Run history, human-review feedback and the other things a tenant exchanges with a portal in
operation — the Ops records, a contract of their own (C8 of
`.agent-rfc/designs/governance-contracts.md`).
