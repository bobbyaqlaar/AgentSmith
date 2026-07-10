# Enterprise Delivery Model

How AgentSmith teams ship agents on **shared, governed rails** — not one-off
“ChatGPT for enterprise” stacks. Maps the consultant Delivery Model needs to
concrete catalogs, soft gates, and promote-time **artifacts**.

> Compliance is demonstrated through logs and artifacts, not slide decks.

**Related:** [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md),
[`docs/uae-regulatory.md`](./uae-regulatory.md),
[`templates/delivery-model/`](../templates/delivery-model/),
[`FIXES_AND_CLEANUP.md`](../FIXES_AND_CLEANUP.md).

---

## Consultant needs → AgentSmith

| # | Need | AgentSmith response |
|---|---|---|
| 1 | Pre-approved envs, data access, security, deploy pipelines | Platform catalog in org policy + tenant `delivery.platform` |
| 2 | Rules in the delivery process, not after | Hooks, eval/redaction CD gates, soft Delivery Model check, evidence pack |
| 3 | Compliance via logs/artifacts | Audit log, Phoenix, eval/fairness scorecards, `delivery_evidence.*` |
| 4 | Standard RAG functions | v1: [`docs/rag-memory.md`](./rag-memory.md) — conversation memory + vector store |

---

## Approved platforms (catalog)

Ids used in `delivery_model.approved_platforms` and tenant `delivery.platform`:

| Platform id | Meaning | Starter |
|---|---|---|
| `dev-local` | Local Ollama / laptop | `AI_STACK_MODE=local` |
| `hybrid-cloud` | Approved cloud providers + shared Phoenix | `runtime/models.yaml` + gateway |
| `on-prem` | Customer hardware / air-gap | [`templates/onprem-deploy/`](../templates/onprem-deploy/) |
| `uae-sovereign` | In-border + Falcon/sovereign API | [`templates/uae-sovereign/`](../templates/uae-sovereign/) |
| `dedicated-k8s` | Dedicated tenant worker pool | `tenant.isolation: dedicated` |

Orgs edit the list in
[`templates/delivery-model/org-policy.example.yaml`](../templates/delivery-model/org-policy.example.yaml)
→ copy to `.agenticframework/org-policy.yaml`.

### Tenant binding

```yaml
# .agenticframework/tenant.yaml
tenant:
  id: acme
  name: Acme Corp
  isolation: shared
delivery:
  platform: on-prem                    # must be in approved_platforms
  data_access_pattern: postgres-tenant-partition
```

---

## Data-access patterns & security controls

Documented in the example org policy:

- **Data access:** `postgres-tenant-partition`, `dedicated-db`, `no-national-data-export`
- **Security:** pre-commit hooks, trace redaction, pre-call input guardrail in
  prod, HITL for high-impact, HMAC audit log
- **Pipelines:** GitHub Actions staging→production, on-prem Compose/Helm

---

## Soft gate

```bash
python3 scripts/verify_system.py --check-delivery-model
```

- No `delivery_model` in org-policy → **skip** (pass)
- Platform / pattern mismatch → **warn** (still exit 0)
- Never hard-fails CI by default

---

## Promote-time evidence pack

```bash
python3 scripts/run-evals.py --fail-below 0.80
ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction
python3 scripts/verify_system.py --check-delivery-model
python3 scripts/delivery_evidence.py
```

Writes:

- `.agent-rfc/fixtures/delivery_evidence.json` — machine-readable manifest
- `.agent-rfc/fixtures/delivery_evidence.md` — auditor-facing summary

Hand these to reviewers with ISO/UAE packs — not a slide deck of intended controls.

---

## Need → gate → artifact

| Need | Gate / process | Artifact |
|---|---|---|
| 1 Approved platform | Soft `--check-delivery-model` | org-policy + tenant.yaml |
| 2 In-process rules | Pre-commit, RFC (enterprise), eval CD, redaction CD, input guardrail | CI logs |
| 3 Evidence not slides | `delivery_evidence.py`, audit API, Phoenix | `delivery_evidence.md/json`, scorecards |
| 4 | RAG | Memory v1 (`docs/rag-memory.md`) | `vector_store.query` hits; tenant wires into prompt |
