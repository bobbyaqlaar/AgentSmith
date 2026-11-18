# The compliance contract, version 1

A **compliance provider** answers whether a repository on a compliance profile meets the obligations of that profile, and records who
signed for the ones only a person can. AgentSmith is one provider.

## What a repository holds

| File | What it is |
|---|---|
| `.agenticframework/compliance.json` | The declaration (`declaration.schema.json`). Its presence is the profile |
| `.agenticframework/attestations.jsonl` | Signatures, one per line (`attestation.schema.json`), appended at a terminal |
| `compliance` in `.agenticframework/process-gates.json` | `{"profile": <name>, "mode": "report"\|"enforce"}`. Enforced profiles only strengthen |

## The protocol

```
<compliance-command> check --stage ci|production
```

- **cwd** is the repository. **stdin** is closed.
- **stdout** is one result: `schema`, `verdict` (`pass` \| `fail` \| `no_profile`), `stage`, `profile`, `reason`, `rows`, `counts`.
- **exit 0** whenever the provider answers. Anything else is no answer, and a caller on a profile treats no answer as a failure.

Each row has an `id` from the catalogue (`obligation.schema.json`), a `result` and a `message`.

| `result` | Means |
|---|---|
| `pass` | Enforced, verified or validly signed |
| `fail` | Not met, and this stage is one the obligation blocks |
| `pending` | Not met, and this stage is not one it blocks; or a provider obligation the provider names as not yet proved |
| `not_applicable` | The provider's own evidence covers it (AgentSmith: `scripts/compliance_port.py provider-evidence`, run by Self-Test and attached to each release), or no control applies here |

An attestation that has expired counts as absent. A declaration that cannot be read is a failure, never "no profile".

## The portal

`POST /api/compliance/sync` with the app's Ops token: the body is `{"attestations": [...]}`, the repository's records, and the answer
is `{"attestations": [...]}`, the ones given in the portal. A signature's `id` makes resending harmless.

## At run time

A deployed application imports `agentsmith.compliance`. On a profile:

- `record()` writes to the database the worker already uses, chained and keyed by `COMPLIANCE_RECORD_KEY`, and `forward()` sends unsent records
  to the portal (`kind: compliance_record`, `contract/ops/v1`) when it is up.
- **No record, no action.** A record that cannot be written raises `ComplianceRefused`, naming the obligation. Only that function stops.
- `run_with_hitl_gate(..., compliance=True)` accepts only a named decision, the `hitl_decide` signal carrying `HumanDecision`. A decision names the `hitl_pending` record it answers (`request_record_id`) and the digest of the input that record showed (`payload_sha256`); on the Temporal path and the store path alike, only a decision naming the latest request with its digest answers it.
- The stop flag lives in the same database, set by the portal over the signed webhook or by `agentsmith ops stop`.
- The portal may be down: runs continue, gates wait, and records queue.

Conformance: `agentsmith conformance --port compliance --provider CMD` runs `cases.json`.
