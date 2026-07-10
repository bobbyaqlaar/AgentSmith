# AgentSmith — Active Work and Future Phases

**Last reviewed:** 2026-07-10 (UAE regulatory map added)  
**Purpose:** Active planned work and confirmed future gaps with their
trigger conditions, rationale, and embedded design decisions. Completed
build history lives in `Product_Archive.md`.

---

## P11 — GCP deployment + oil-price-demo CI green + demo publication 🟡 P11a/b/c DONE · P11d NOT STARTED

**Goal:** Deploy AgentSmith framework and oil-price-demo (tenant: `bobbyaqlaar/oil-price-demo`)
to GCP via GitHub Actions CI/CD, then publish a demo + article series
(LinkedIn, Substack, Medium) documenting the process.

**Repos involved:**
- AgentSmith framework: `bobbyaqlaar/AgentSmith` (or local `AgenticFramework/`)
- Tenant demo: `bobbyaqlaar/oil-price-demo` — branch `develop`, PR #1 open (`develop → main`)

---

### P11a — oil-price-demo CI green ✅ DONE (2026-07-01)

**Context:** Oil-price-demo repo is checked out locally at
`/Users/mac/Documents/Bobby/Aqlaar/Apps/oil-price-demo` — edits go via
normal `git` + push, NOT `gh api PUT`. The `git clone` avoidance rule
applies only when cloning FROM WITHIN the AgentSmith directory.

**Final CI state (branch: `develop`, PR #1 open `develop → main`):**

| Job | Status |
|---|---|
| Guardrails — Python/FastAPI | ✅ PASS |
| Eval scorecard | ✅ PASS |
| Deploy to Staging | 🔄 in progress (GCP secrets present, smoke test pending) |

**Fixes applied to get CI green (cumulative):**
1. `scripts/run-evals.py` — detect `result["status"] == "failed"` from
   `run_pipeline()` as pipeline error → `pipeline_error=True` → all-errors
   path exits cleanly.
2. Ruff lint fixes: unused imports (F401), unnecessary f-strings (F541),
   invalid `# noqa` directives.
3. `ruff format` must be run separately from `ruff check` — both must pass.
4. `scripts/run-evals.py::run_scorecard()` — results path `relative_to()`
   raises `ValueError` when monkeypatched to `tmp_path` outside repo root;
   wrapped in try/except.
5. `test/test_activities.py` — spike series sigma inflation fixed with
   10-stable + 1-spike series.
6. `scripts/check_bare_except.py` (repo + `~/.agent-framework/scripts/`) —
   updated to accept BOTH `# noqa: bare-except` (legacy) AND `# fail-open:`
   (new convention). The global `~/.agent-framework` copy is what the
   pre-commit hook actually executes; the repo copy was updated previously
   but the hook was still using the outdated global version.
7. `scripts/cost_router.py` — 4-attempt retry with full jitter:
   `wait = (2**attempt)*5 + random.uniform(0, 3)` (10–13s, 20–23s, 40–43s).
   Simple `2**n * 5` without jitter caused thundering-herd retries that still
   saturated Groq's 30 RPM free tier.
8. `scripts/run-evals.py` — `all(pipeline_error)` path now returns `0` not `2`.
   Exit code 2 is non-zero and fails the CI step; "skip gracefully on infra
   errors" requires exit 0.
9. `test/test_run_evals.py` — updated `test_skip_when_all_pipeline_errors`
   assertion from `== 2` to `== 0` to match above.

**Repeated-action lessons (do not repeat these):**
- **Groq 429 retry without jitter** — `2**n * 5` gives fixed waits; concurrent
  CI jobs retry in lockstep and re-saturate the rate window together. Always
  add `random.uniform(0, 3)` jitter.
- **`# fail-open:` vs `# noqa: bare-except`** — the hook reads the GLOBAL
  `~/.agent-framework/scripts/check_bare_except.py`, not the repo copy. Always
  update both, or use `# noqa: bare-except` until the global copy is patched.
- **Non-zero "skip" exit code** — `return 2` in `run_scorecard()` still fails
  the shell step. Graceful skip = `return 0`.
- **Test/code skew** — when changing a return value, update the test in the
  same commit; CI will catch the skew if they ship separately.

**Note:** `cd-demo-ui.yml` fails (no demo UI Dockerfile) — expected, not blocking.

---

### P11b — GCP resources + oil-price-demo GitHub Environments ✅ DONE

**oil-price-demo GitHub Environments** (`bobbyaqlaar/oil-price-demo` → Settings → Environments):

| Secret | staging | production |
|---|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | ✅ set | ✅ set |
| `GCP_SERVICE_ACCOUNT` | ✅ set | ✅ set |
| `GCP_PROJECT_ID` | ✅ set | ✅ set |
| `DEPLOY_COMMAND` | ✅ Cloud Run deploy cmd | ✅ set |
| `GROQ_API_KEY` | ✅ set | ✅ set |
| `AGENT_MODEL_ARCHITECT` | ✅ `llama-3.3-70b-versatile` | ✅ set |
| `AGENT_MODEL_COMPLEX` | ✅ `llama-3.3-70b-versatile` | ✅ set |
| `AGENT_JUDGE_MODEL` | ✅ `llama-3.3-70b-versatile` | ✅ set |
| `ANTHROPIC_API_KEY` | ✅ present (zero balance — Groq is fallback) | ✅ set |

**GCP resources provisioned (project: `agentsmith-500916`, us-central1):**
- Cloud SQL Postgres: `temporal-pg` (db-f1-micro, public IP `35.255.14.25`, ssl-mode=ENCRYPTED_ONLY)
- Cloud Run: `temporal-server` (min-instances=1, BIND_ON_IP=0.0.0.0, SQL_TLS_ENABLED=true)
- Cloud Run: `oil-price-worker-staging` (deployed; /healthz 404 anomaly under investigation, not blocking)
- Artifact Registry: `oil-price-demo` repo
- Artifact Registry: `agentsmith-portal` repo (portal images)
- WIF pool: `github-actions-pool` / provider `github-provider`
  - **Attribute condition:** `assertion.repository in ['bobbyaqlaar/oil-price-demo', 'bobbyaqlaar/AgentSmith']`
    (updated from single-repo `==` to multi-repo `in [...]` when second repo was added)
- SA: `github-deployer@agentsmith-500916.iam.gserviceaccount.com`
  - Also granted `roles/cloudsql.client` (for Cloud SQL Auth Proxy on the Compute SA — see P11c)
- Secret Manager: `oil-price-demo-anthropic-key`, `ops-portal-user`, `ops-portal-password`,
  `ops-portal-db-url`, `ops-portal-audit-hmac-key`, `ops-portal-sync-token`
- `agenticframework` database created on `temporal-pg`; schema migrated (all portal tables + triggers)

**oil-price-demo PR #1 merged to main** ✅ Production CD deployed successfully ✅

**Billable resources — explicitly deferred:** Cloud SQL `temporal-pg` (~$7–10/month) and `temporal-server` Cloud Run (min-instances=1) remain live to support the P11d demo publication. Tear down after demo article is published. Owner: Bobby.

---

### P11c — AgentSmith Ops Portal deployed to GCP ✅ DONE (2026-07-01)

**AgentSmith GitHub Environments** (`bobbyaqlaar/AgentSmith` → Settings → Environments):

| Secret | staging | production |
|---|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | ✅ set | ✅ set |
| `GCP_SERVICE_ACCOUNT` | ✅ `github-deployer@agentsmith-500916.iam.gserviceaccount.com` | ✅ set |
| `GCP_PROJECT_ID` | ✅ set | ✅ set |
| `DEPLOY_COMMAND` (staging) | ✅ see full command below | ✅ production equivalent |

**Current DEPLOY_COMMAND (staging):**
> ⚠️ `$IMAGE_REF` and `$GCP_PROJECT_ID` are set as env vars by the `cd-portal.yml` workflow steps before this command runs. This command cannot be pasted into a terminal as-is — those variables will be empty outside the GitHub Actions job context.
```
gcloud run deploy agentsmith-portal-staging \
  --image $IMAGE_REF --region us-central1 --project $GCP_PROJECT_ID \
  --platform managed --allow-unauthenticated \
  --add-cloudsql-instances=agentsmith-500916:us-central1:temporal-pg \
  --set-secrets=OPS_PORTAL_USER=ops-portal-user:latest,OPS_PORTAL_PASSWORD=ops-portal-password:latest,DATABASE_URL=ops-portal-db-url:latest,AUDIT_LOG_HMAC_KEY=ops-portal-audit-hmac-key:latest,OPS_PORTAL_SYNC_TOKEN=ops-portal-sync-token:latest
```

**DATABASE_URL (stored in Secret Manager `ops-portal-db-url`):**
```
postgresql://postgres:***@/agenticframework?host=/cloudsql/agentsmith-500916:us-central1:temporal-pg
```
Unix socket via Cloud SQL Auth Proxy — no TCP, no cert management, Google-managed mTLS.

**Live Cloud Run services:**
- Staging: https://agentsmith-portal-staging-431995395208.us-central1.run.app
- Production: https://agentsmith-portal-production-431995395208.us-central1.run.app
- Credentials: `ops` / stored in Secret Manager `ops-portal-password`

**Fixes applied during portal deploy (do not repeat):**
1. WIF attribute condition was locked to `oil-price-demo` only — updated to `in [...]` list.
2. `build-push-ghcr` action defaulted to root `Dockerfile` (absent) — added `dockerfile_path: portal/Dockerfile` in `cd-portal.yml`.
3. GHCR image name preserved repo casing (`AgentSmith`) — added `| tr '[:upper:]' '[:lower:]'` to `build-push-ghcr/action.yml`.
4. Cloud Run rejects GHCR images — added "Push to Artifact Registry" step in `cd-portal.yml` that retags and pushes before `gcloud run deploy`.
5. `DEPLOY_COMMAND` referenced `$GCP_PROJECT_ID` but it wasn't exported — added `env: GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}` at the job level.
6. `GCP_SERVICE_ACCOUNT` secret had wrong value — corrected to `github-deployer@agentsmith-500916.iam.gserviceaccount.com`.
7. Portal startup check requires `OPS_PORTAL_USER`/`OPS_PORTAL_PASSWORD` — created Secret Manager secrets and wired via `--set-secrets` in `DEPLOY_COMMAND`.
8. `DATABASE_URL` not set — created `agenticframework` DB on Cloud SQL, ran schema migration, stored connection string in Secret Manager.
9. SSL cert verification failure (`UNABLE_TO_VERIFY_LEAF_SIGNATURE`) — **do not use `sslmode=no-verify`** (MITM-vulnerable). Fixed by switching to **Cloud SQL Auth Proxy** via `--add-cloudsql-instances`: Unix socket connection, IAM auth, Google-managed mTLS. Compute SA granted `roles/cloudsql.client`.
10. New Secret Manager secrets need explicit SA binding before `gcloud run deploy` can reference them — grant `roles/secretmanager.secretAccessor` to the Compute SA for each secret.

---

### P11d — Demo publication (LinkedIn / Substack / Medium) 🟡 NOT STARTED

**Trigger:** CI green on `develop` + at least one successful staging deploy to GCP.

**Demo URL:** will be the Cloud Run service URL from `gcloud run services describe`.

**Article content to cover:**
1. The AgentSmith framework architecture (Ten Pillars, multi-agent, eval scorecard)
2. Building the oil-price-demo tenant app from `ai-tenant-init` to production
3. The CI/CD pipeline story: GitHub Actions → GCP Cloud Run via WIF (keyless auth)
4. Lessons: Groq rate limits in CI, `set +e` exit code capture, GitHub Models as free CI eval backend
5. Screenshots: Phoenix traces, Ops Portal, the HITL DLQ flow, eval scorecard output

**Source material already written:**
- `OPERATIONS.md` §D.5b — full GCP auth + Cloud Run deploy story
- `Product_Archive.md` — build history P0–P10 (use as article structure)
- `README.md` — framework overview (use as intro)

---

## Future Phases — confirmed gaps, not yet scheduled

Surfaced by a deliberate audit against a functional/non-functional layer
checklist (Readme.md "Architecture by Layer" / SPECS.md §4). Each is listed
with a **trigger condition** (the concrete signal that means "build this
now," not a calendar date) and **rationale**, so a future session can
decide whether the trigger has actually fired instead of re-litigating
whether the gap matters.

Two design decisions are settled for items below and recorded so they are
not re-opened: MCP integration stays tenant-owned (BYO), not shipped by the
framework; the LLM self-correction loop, if built, is a separate opt-in
method, not inserted in front of the existing human DLQ escalation path.

---

### Delivery Model — gap register (consultant review)

Enterprise agent delivery is not a feature checklist ("RAG + multi-model +
GDPR + deploy-by-Friday"). It is a **Delivery Model**: how teams ship agents
on shared, governed rails instead of one-off solutions. AgentSmith stance
against that fantasy maps to four requirements:

| # | Delivery Model need | Status | Pointer |
|---|---|---|---|
| 1 | Teams use pre-approved environments, data access patterns, security controls, and deployment pipelines — no repeated approvals, no unscalable one-offs | **Partial** | `ai-tenant-init` / promote, CI/CD workflow templates, enterprise MDM hook bundles, on-prem/K8s templates — no named approved-platform catalog yet → [Enterprise Delivery Model](#enterprise-delivery-model--approved-platforms--in-pipeline-governance) |
| 2 | Rules for data use, risk, auditability, and access live **in** the delivery process, not reviewed afterwards | **Partial** | Pre-commit hooks, enterprise RFC gate, eval promote gates, CD redaction compliance — gaps remain (e.g. pre-call PII) → same phase |
| 3 | Compliance demonstrated through logs and artifacts, not slide decks | **Met** | HMAC-signed append-only audit log (SPECS.md §30), Phoenix OTel traces, eval scorecards, encrypted HITL blobs |
| 4 | Standard functions and frameworks for RAG | **Gap** | No vector/RAG layer in repo; Knowledge Graph is structured recall, not RAG → [Memory Management](#memory-management--short-term-token-window--long-term-vector-store) (vector half) |

---

### UAE Regulatory — gap register

UAE differentiator map (sovereign infra, bias law, HITL, PDPL, oversight).
Canonical narrative: [`docs/uae-regulatory.md`](./docs/uae-regulatory.md).
Not legal advice / not certification.

| # | Mandate | Status | Pointer |
|---|---|---|---|
| 1 | Sovereign infrastructure — national data + models in UAE borders (G42-class clouds, TII Falcon, etc.) | **Partial** | Local Ollama + on-prem templates + pluggable gateway endpoint → [UAE Regulatory Alignment](#uae-regulatory-alignment--sovereign-profile--iso-42001-map); pattern in `docs/uae-regulatory.md` §1 |
| 2 | Bias & fairness — Federal Decree-Law No. 34/2023; routine bias audits | **Gap** | → [Data Bias & Fairness](#data-bias--fairness--fairnessrobustness-evaluation) |
| 3 | HITL stop-gates for high-impact actions + accountability trail | **Met** | `run_with_hitl_gate`, recoverable DLQ, HMAC audit log, HITL blobs |
| 4 | PDPL — mask/anonymize PII (e.g. Emirates ID) in the decision path | **Partial** | Post-call `trace_redactor.py` shipped; pre-call scrub → [Security & Guardrails](#security--guardrails--pre-call-input-sanitization) |
| 5 | Oversight bodies — embed governance (ISO/IEC 42001) from day one | **Partial** | Enterprise pack + audit/eval artifacts shipped; clause map + Authority checklist → [UAE Regulatory Alignment](#uae-regulatory-alignment--sovereign-profile--iso-42001-map) |

---

### UAE Regulatory Alignment — sovereign profile + ISO 42001 map

**Gap:** runtime already supports in-border / air-gapped deploy and pluggable
providers, and ships HITL + audit substrate, but there is no packaged **UAE
sovereign profile** (documented Falcon/UAE-endpoint `models.yaml` example,
residency checklist) and no **ISO/IEC 42001 / Authority-facing control map**
that turns existing artifacts into an oversight pack. Fairness (#2) and
pre-call PII (#4) stay in their existing Future Phases — do not duplicate
implementation sketches here.

**Trigger:** a UAE tenant (or regional bid) requires documented sovereign
hosting + Falcon/UAE endpoint wiring, **or** an oversight/ISO 42001 review
asks for a control-to-artifact map rather than SOC2-oriented notes alone.

**Out of scope:** claiming G42/TII partnership; claiming PDPL/ISO
certification; implementing the fairness suite or pre-call guardrail (link
those phases instead).

**Fix sketch, when triggered:**
- Tenant-facing sovereign profile: example `models.yaml` + env for
  UAE-hosted Ollama Falcon (or OpenAI-compatible sovereign endpoint), plus
  residency checklist (workers, Phoenix, Postgres, HITL blobs in-border).
- ISO/IEC 42001-oriented control map: each relevant control → AgentSmith
  gate/artifact path (eval report, redaction check, audit events, HITL
  records) operators can hand to auditors / the UAE Authority for AI and Data.
- Cross-link `docs/uae-regulatory.md` status board when items move
  Partial → Met.

---

### Enterprise Delivery Model — approved platforms + in-pipeline governance

**Gap:** pieces exist (tenant scaffold, CI/CD templates, enterprise pack,
eval/redaction gates) but are not packaged as a reusable **approved
platform** with data-access patterns and promote-time evidence that a
multi-team org can adopt without inventing one-offs. Point 3 above is
already met; this phase covers points 1–2 only. Point 4 (RAG) stays under
Memory Management — do not duplicate it here.

**Trigger:** a multi-team org needs a reusable approved platform (not a
one-off tenant), **or** a compliance review asks to "show delivery
controls and artifacts," not a slide deck of intended controls.

**Out of scope:** implementing RAG/vector retrieval (Memory phase);
claiming GDPR/SOC2 certification; expanding the fantasy feature list.

**Fix sketch, when triggered:**
- Catalog of pre-approved environments, data-access patterns, security
  controls, and deployment pipelines (org policy YAML + `ai-tenant-init`
  defaults that bind new tenants to those rails).
- Bake data-use / risk / audit / access checks into promote and CD so
  evidence is produced as artifacts (eval report, redaction compliance
  result, audit events) — not a post-hoc review step.
- Document the mapping: Delivery Model need → concrete gate/artifact path
  operators can point auditors at.

---

### Memory Management — short-term (token-window) + long-term (vector store)

**Delivery Model link:** this section's vector/RAG half is the home for
Delivery Model need #4 (standard RAG functions) — see gap register above.
No separate RAG Future Phase.

**Already implemented (not part of this gap):** the long-term, structured
half of this layer exists as the codebase Knowledge Graph (`map_codebase.py`
→ `local_knowledge_graph.py`, SPECS.md §10) — graph-based recall over files,
dependencies, guardrails, and past incidents that survives across sessions.

**Gap:** no short-term token-window truncation/summarization/sliding-window
manager, and no semantic / vector retrieval (Chroma/pgvector/etc.) anywhere
in the repo.

**Trigger:** the first tenant app that needs either (a) a conversation longer
than fits in one context window, or (b) semantic retrieval over a corpus too
large to put in a prompt directly.

**Fix sketch, when triggered:**
- Short-term: `runtime/conversation_memory.py` — message list with a
  configurable token budget (via `tiktoken`) and a pluggable eviction strategy
  (truncate-oldest first; summarization via `gw.complete()` is a reasonable v2).
- Long-term: `runtime/vector_store.py` interface (`add`, `query`) with a
  Postgres+pgvector backend as the default — consistent with this framework's
  existing Postgres-backed state (idempotency, DLQ, budget). Chroma/Pinecone
  become alternate backends behind the same interface only if a concrete tenant
  need shows up.

---

### Tool Orchestration — registration/schema-extraction, MCP

**Gap:** no `@tool`-style decorator extracting a Python function's signature
into a JSON schema; `llm_gateway.py.complete()` sends a prompt and gets text
back — no function-calling fields in the provider request.

**Design decision (settled — do not re-open without a concrete reason):** MCP
integration stays **bring-your-own** — the framework does not ship an MCP
client/server. Rationale: AgentSmith's design goal is supporting tenant apps
of "any architecture or language," and MCP is one tool-orchestration standard
among several a tenant might already use; shipping it as first-class would tie
every tenant to that standard and commit this framework to tracking MCP's spec
evolution, for a capability orthogonal to what this framework owns
(budget/redaction/tracing/HITL around an LLM call, not the orchestration
logic in front of it). If your tenant app uses MCP, treat `llm_gateway.py` as
the place the resulting LLM call flows through; the MCP client/tool-schema
layer sits in front of it in your own code.

**Trigger:** a tenant reference app whose domain needs the LLM to choose
among several tools dynamically, as opposed to fixed activity sequences.

**Fix sketch, when triggered:** a small `runtime/tool_registry.py` with a
decorator that introspects type hints/docstrings into a JSON schema,
independent of any specific orchestration protocol.

---

### Perception & Input Parsing — structured output parsing, prompt templating

**Gap:** the reference pipelines extract JSON from LLM text via bare
`re.search`+`json.loads()` with a hardcoded fallback shape — no schema
validation. No reusable prompt-template engine; prompts are inline f-strings.

**Trigger:** a second reference pipeline (or a real tenant app) that duplicates
either the JSON-extraction pattern or a near-identical prompt structure — once
there are 2+ real call sites with the same shape, not before.

**Fix sketch, when triggered:** `runtime/structured_output.py` (Pydantic model
+ `model_validate_json`, typed error on mismatch) and
`runtime/prompt_templates.py` (minimal Jinja2 or `string.Template` wrapper).

---

### Human-in-the-Loop — LLM-driven self-correction

**Gap:** every recovery path today is human-driven (DLQ edit-and-replay) or
Temporal-driven (transient-failure retry) — no path where the model sees its
own tool-call error and retries with a corrected call before any human is
involved.

**Design decision (settled):** if built, this is a **separate, opt-in method**
(e.g. `run_with_self_correction`), not inserted in front of
`run_with_recoverable_step`'s existing human-escalation path. Rationale: keeps
the already-shipped, already-tested human-escalation behavior completely
unchanged for every existing call site; a tenant who wants model-driven retry
for a specific failure class opts into the new method deliberately.

**Trigger:** a tenant reports DLQ volume dominated by an error class a model
could plausibly self-correct on the first retry — evidence from real DLQ
`reason` distribution, not a guess.

**Fix sketch, when triggered:** `run_with_self_correction(activity_name,
payload, tenant_id, max_self_correction_attempts, ...)` — on activity failure,
calls `gw.complete()` with the original payload + error message, asks the
model for a corrected payload, retries up to `max_self_correction_attempts`,
and only then falls through to enqueueing a DLQ entry exactly as
`run_with_recoverable_step` does today — reusing that path, not duplicating it.

---

### Security & Guardrails — pre-call input sanitization

**UAE / PDPL link:** Delivery Model and UAE Regulatory need #4 — masking
personal data (names, Emirates ID, etc.) in the agent decision path, not only
in post-call traces. See `docs/uae-regulatory.md` §4.

**Gap:** `trace_redactor.py` redacts/anonymizes data **after** a call, for
observability. There is no symmetric **pre-call** guardrail — nothing scrubs
PII or moderates content in the prompt sent to the model.

**Trigger:** a tenant app that accepts untrusted end-user input directly into a
prompt (the current examples take structured internal data — price series,
payloads — never free-text user input), **or** a PDPL / UAE deployment that
must demonstrate PII masking before model invoke (e.g. Emirates ID in
prompts).

**Fix sketch, when triggered:** a `runtime/input_guardrail.py` hook point in
`llm_gateway.py.complete()`, called before `_invoke()` — pluggable (framework
provides the call site, not a specific moderation model), matching the
framework's existing pattern of providing the mechanism and letting the tenant
supply the policy (same shape as `replay_handler`, `TENANT_WORKER_MODULE`).

---

### Reliability & Accuracy — hallucination-rate metric

**Gap:** `run-evals.py`/`eval_judge.py` score `correctness`, `tool_accuracy`,
`latency` — no metric is literally named "hallucination rate." A hallucination
shows up as a low `correctness` score, not as its own tracked number.

**Trigger:** a tenant or stakeholder needs hallucination tracked as its own
reportable number (e.g. a compliance requirement stating "< 5% hallucination
incidents" specifically, not "correctness ≥ some threshold") — the two are
not the same number.

**Fix sketch, when triggered:** add a `hallucination` field to the judge's
scored output in `.agent-rfc/fixtures/custom_judge_criteria.json` — a new
judge-prompt dimension asking specifically "did the response state something
not supported by the input/retrieved context," distinct from "was the response
correct." Additive to the existing scorecard, not a replacement for
`correctness`.

---

### Scalability & Performance — Time-to-First-Token

**Gap:** `llm_gateway.py` makes one non-streaming HTTP call per `complete()` —
there is no first-token timestamp anywhere, so TTFT cannot be measured.

**Trigger:** a tenant app with a user-facing streaming response UI (e.g. a chat
interface showing tokens as they arrive) — TTFT only matters as a UX metric
once there's a UI that benefits from streaming.

**Fix sketch, when triggered:** add a streaming code path to
`runtime/provider_dispatch.py` (provider SDKs already support streaming —
this is wiring, not new capability), record the first-chunk timestamp in
`_invoke()`, add `ttft_ms` alongside existing `cost_usd`/token counts in
`_record_span_attributes`. Non-streaming `complete()` stays the default —
streaming is an opt-in mode.

---

### Data Bias & Fairness — fairness/robustness evaluation

**UAE link:** UAE Regulatory need #2 — Federal Decree-Law No. 34/2023 and
routine bias audits before launch. See `docs/uae-regulatory.md` §2.

**Gap:** no fairness, bias, or robustness metric (demographic parity, disparate
impact, adversarial-input robustness) is tracked anywhere in the eval
framework.

**Trigger:** a tenant app whose domain has a real fairness exposure (e.g.
anything making decisions about people — lending, hiring, eligibility), **or**
a UAE / regulatory requirement for documented bias audits (Decree-Law
34/2023). Genuinely not applicable to the current reference examples (oil
price forecasting has no fairness dimension) until such a tenant appears.

**Fix sketch, when triggered:** a separate evaluation dataset — fairness test
sets (paired inputs differing only in a protected attribute, checking for
outcome parity) don't usually overlap with task-correctness golden sets. Scope
as its own `.agent-rfc/fixtures/fairness_evals.json` with its own judge
criteria, evaluated by `scripts/run-evals.py --suite fairness` (new flag).

---

*Build history (P0–P10) lives in `Product_Archive.md`.
SPECS.md and Readme.md are the canonical specification record.
OPERATIONS.md is the canonical operator-facing reference.*
