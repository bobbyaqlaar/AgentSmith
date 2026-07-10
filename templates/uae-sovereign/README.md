# UAE Sovereign Profile (sketch)

Tenant-facing starter for **in-border** AgentSmith deployments that must
satisfy UAE data-residency expectations: national data and model inference
stay on UAE-hosted (or on-prem) infrastructure, with TII Falcon (or a
sovereign OpenAI-compatible endpoint) as the primary model path.

**Not a G42/TII partnership. Not a certification.** Copy into a tenant repo,
replace placeholders, and have counsel confirm the residency story.

Canonical mandate map: [`docs/uae-regulatory.md`](../../docs/uae-regulatory.md).
On-prem runtime packaging: [`templates/onprem-deploy/`](../onprem-deploy/).

---

## What this folder contains

| File | Purpose |
|---|---|
| `models.yaml` | Example tenant model registry — Falcon via UAE-hosted Ollama, plus optional sovereign OpenAI-compatible API role |
| `env.example` | Env vars for local mode, in-border Ollama/API URL, storage, redaction |
| `README.md` | This file — residency checklist + wire-up steps |

Copy into a tenant repo root (or `.agenticframework/`) as needed:

```bash
cp templates/uae-sovereign/models.yaml /path/to/tenant/models.yaml
cp templates/uae-sovereign/env.example /path/to/tenant/.env.uae.example
# merge env.example into the tenant's real .env / secret store — never commit secrets
```

---

## Wire-up (two supported patterns)

### Pattern A — Falcon on UAE-hosted Ollama (default in `models.yaml`)

1. Run Ollama on **in-border** compute (on-prem VM, UAE-region K8s node, or
   sovereign cloud GPU).
2. Pull / import Falcon (verify current tags before production):

   ```bash
   # Official Ollama library (TII Falcon family — confirm tag on ollama.com)
   ollama pull falcon2          # Falcon 2 ~11B — common general-purpose choice
   # ollama pull falcon:7b      # smaller
   # ollama pull falcon:40b     # needs ~32GB+ RAM

   # Newer TII weights not in the library yet → GGUF + Modelfile import
   # (see https://docs.ollama.com/import) then set models.yaml id to that name.
   ```

3. Set `AI_STACK_MODE=local` and point `OLLAMA_BASE_URL` at the **in-border**
   Ollama base (no `/v1` suffix — `models.yaml` appends `/v1`).
4. Place this folder’s `models.yaml` at the tenant repo root so
   `runtime/llm_gateway.py` loads it over framework defaults.

### Pattern B — Sovereign OpenAI-compatible API

If your UAE provider (e.g. a G42-class cloud) exposes an OpenAI-compatible
chat completions URL:

1. Set `UAE_SOVEREIGN_API_BASE` and `UAE_SOVEREIGN_API_KEY` (see `env.example`).
2. Uncomment / prefer the `sovereign_api` role in `models.yaml`.
3. Keep Postgres, Phoenix, HITL blobs, and workers on the same in-border
   footprint — moving only the model API in-border is not enough if traces
   and databases leave the country.

Hybrid mode to **non-UAE** frontier APIs (Anthropic/OpenAI/Groq public) is
**out of profile** for national data unless counsel explicitly approves.

---

## Data residency checklist

Tick before production with national or personal data. Evidence belongs in
ops runbooks / audit packs — not slide decks.

### Compute & inference

- [ ] Worker / Temporal / agent processes run in UAE region or on-prem in UAE
- [ ] LLM endpoint is in-border Ollama **or** UAE sovereign API (Pattern A/B)
- [ ] `AI_STACK_MODE=local` (or hybrid only to in-border endpoints)
- [ ] No degrade ladder hop to public non-UAE frontier APIs for national data
      (edit `degrade_to` in tenant `models.yaml` accordingly)

### Data stores

- [ ] `DATABASE_URL` Postgres in UAE / on-prem (portal, budget, DLQ, audit)
- [ ] Redis (if `BUDGET_BACKEND=redis`) in same residency boundary
- [ ] Phoenix / OTLP endpoint in-border (`AGENT_PHOENIX_ENDPOINT`)
- [ ] `HITL_BLOB_DIR` or `HITL_BLOB_S3_BUCKET` on in-border object storage
- [ ] Trace redaction profile = staging/production (not passthrough)

### Access & governance

- [ ] High-impact activities use `run_with_hitl_gate` / recoverable DLQ
- [ ] Ops Portal audit log reachable; `AUDIT_LOG_HMAC_KEY` set
- [ ] Break-glass / hook bypass (if enterprise pack) audited
- [ ] PII (Emirates ID, names) scrubbed **before** gateway until pre-call
      guardrail ships — see FIXES Security & Guardrails
- [ ] Fairness/bias evidence plan if agent decides about people — see FIXES
      Data Bias & Fairness + `docs/uae-regulatory.md` §2

### Deploy packaging

- [ ] Prefer [`templates/onprem-deploy/`](../onprem-deploy/) or sovereign-cloud
      K8s for the app image — air-gap friendly, no required cloud metadata calls
- [ ] Secrets via in-border secret store / K8s Secret — not a foreign SaaS vault
      for national data keys

---

## Related

- [`docs/uae-regulatory.md`](../../docs/uae-regulatory.md) — five UAE mandates
- [`FIXES_AND_CLEANUP.md`](../../FIXES_AND_CLEANUP.md) — UAE Regulatory Alignment
- [`runtime/models.yaml`](../../runtime/models.yaml) — framework defaults + endpoint notes
- [`OPERATIONS.md`](../../OPERATIONS.md) — local vs hybrid, on-prem, portal
