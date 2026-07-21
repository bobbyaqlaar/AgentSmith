# AgentSmith — Remaining To-Do Items

**Last reviewed:** 2026-07-15 (P12 security compliance harness shipped)

> **Scope:** this document owns only *not-yet-done* work: the active phase
> and confirmed future gaps with their trigger conditions. Completed build
> history (P0–P11c, phase deliverables) lives in `Product_Archive.md`.
> The formal specification is `SPECS.md`; operator procedures are
> `OPERATIONS.md`.

Each future item records a **trigger condition** (the concrete signal that
means "build this now," not a calendar date) and rationale, so a future
session can decide whether the trigger has actually fired instead of
re-litigating whether the gap matters.

**Settled design decisions (do not re-open without a concrete reason):**
- MCP integration stays tenant-owned (BYO) — the framework does not ship an
  MCP client/server. Rationale recorded in SPECS.md §4a and below.
- LLM self-correction shipped as a separate opt-in method
  (`run_with_self_correction`), never inserted in front of the existing
  human DLQ escalation path.

---

## P11d — Demo publication (LinkedIn / Substack / Medium) 🟡 NOT STARTED

**Goal:** publish a demo + article series documenting AgentSmith and the
oil-price-demo tenant (`bobbyaqlaar/oil-price-demo`) built on it.
P11a/b/c (CI green, GCP resources, portal deploy) are done — see
`Product_Archive.md` §P11.

**Trigger:** already fired (CI green + staging deploys succeeded 2026-07-01).

**Demo URL:** the Cloud Run service URL from `gcloud run services describe`.

**Article content to cover:**
1. The AgentSmith framework architecture (Ten Pillars, multi-agent, eval scorecard)
2. Building the oil-price-demo tenant app from `ai-tenant-init` to production
3. The CI/CD pipeline story: GitHub Actions → GCP Cloud Run via WIF (keyless auth)
4. Lessons: Groq rate limits in CI, `set +e` exit-code capture, GitHub Models as free CI eval backend
5. Screenshots: Phoenix traces, Ops Portal, the HITL DLQ flow, eval scorecard output

**Source material:** `OPERATIONS.md` (GCP deploy story),
`Product_Archive.md` (build history P0–P11, use as article structure),
`README.md` (framework overview, use as intro).

**Cost note:** Cloud SQL `temporal-pg` (~$7–10/month) and `temporal-server`
Cloud Run (min-instances=1) stay live to support this demo. Tear down after
the article is published. Owner: Bobby.

---

## P12 — Security Compliance Harness ✅ DONE (2026-07-15)

**Goal:** reusable test harness covering **OWASP LLM**, **NIST AI RMF**,
**MITRE ATLAS**, and **ISO/IEC 42001**, plus close security gaps (prompt
injection, structured output, tool allowlist, adversarial eval, moderation
hook, SSO fail-closed).

**Shipped:**
- [`docs/security-framework-map.md`](./docs/security-framework-map.md) — live `SEC-*` status
- `scripts/run-security-checks.py` + `fixtures/security/control_registry.json`
- `workflow-templates/eval-security.yml` + framework self-test `strict: true`
- Runtime: `prompt_guard`, `structured_output`, `tool_registry`, `moderation`
- `run-evals.py --suite adversarial`; `SSO_REVOCATION_MODE=fail-closed`

**Strict CI:** framework self-test + tenant Python template use `strict: true`.
Set `MODERATION_HOOK=required` for regulated tenants; default CI env is `optional`.

Remaining Partial/Org-owned rows stay in the security map (RBAC matrix runner,
RAG poison fixture, sovereign smoke, etc.) — not P12 blockers.

---

## Future Phases — confirmed gaps, not yet scheduled

### Compliance gap status boards (pointers, not copies)

Live status for the two compliance tracks is maintained in one place each —
do **not** duplicate their tables here:

- **UAE Regulatory** (sovereign infra, bias law, HITL, PDPL, oversight):
  [`docs/uae-regulatory.md`](./docs/uae-regulatory.md) +
  [`docs/iso-42001-control-map.md`](./docs/iso-42001-control-map.md).
  Still open there: live verification against a *named* UAE sovereign API
  (beyond the verified Ollama Falcon 3 pattern), and org-level certification
  work (never framework-owned).
  **Trigger:** a bid requires a live sovereign-endpoint verification, or an
  auditor demands a licensed clause-ID matrix beyond the thematic pack
  (engage a certification body — out of scope for inventing clause text).
- **Enterprise Delivery Model** (approved platforms, in-pipeline governance):
  [`docs/delivery-model.md`](./docs/delivery-model.md). v1 soft pack
  shipped. Still open: hard-fail enterprise mode; auto-inject `delivery.*`
  defaults from `ai-tenant-init`; CD step uploading the evidence pack as a
  release artifact.
  **Trigger:** an org wants promote blocked when a platform isn't approved,
  or tenant-init must stamp `delivery.platform` automatically.

### Tool Orchestration — provider function-calling wire-up

**Shipped (P12):** `runtime/tool_registry.py` (`@tool` + YAML allowlist,
`SEC-TOOL-001`). MCP stays **bring-your-own** (settled).

**Remaining gap:** `llm_gateway.complete()` still does not emit provider
function-calling request fields — registry is allowlist/schema extraction,
not an MCP/tool-choice runtime.

**Trigger:** a tenant reference app needs the LLM to choose among tools
dynamically inside the gateway request, not only fixed activity sequences.

### Perception & Input Parsing — prompt templating

**Shipped (P12):** `runtime/structured_output.py` (`parse_llm_json`,
`SEC-OUTPUT-001`).

**Remaining gap:** no reusable prompt-template engine; prompts are often
inline f-strings. Reference apps may still use ad-hoc JSON extraction until
migrated to `parse_llm_json`.

**Trigger:** 2+ real call sites sharing the same prompt structure.

**Fix sketch:** `runtime/prompt_templates.py` (minimal Jinja2 or
`string.Template` wrapper).

### Memory / RAG — remaining extensions (v1 shipped)

Shipped v1: `conversation_memory.py`, `embeddings.py` (hash / optional
sentence-transformers), `vector_store.py` (memory / pgvector). See
[`docs/rag-memory.md`](./docs/rag-memory.md) and OPERATIONS.md.

**Remaining:** summarization eviction; auto-RAG in the gateway;
ingest/chunk CLI; live pgvector CI job (extension often absent in bare
Postgres).

**Trigger:** a tenant needs summarization or gateway-native retrieve.

### HITL self-correction — remaining extensions (v1 shipped)

**Remaining:** tenant-specific policies for which error classes opt in;
multi-turn planner/tool-choice correction stays out of scope.

### Eval suites — remaining extensions (v1 shipped)

- **Hallucination:** expand golden cases beyond seed pairs; human review UI
  for flagged cases.
- **Fairness:** domain-specific sets beyond seed pairs; statistical
  disparate-impact metrics beyond judge + pair parity.
- **TTFT:** portal chat UI streaming; TTFT on the non-stream path (not
  measurable without a fake first token).

### Input guardrail — remaining extensions (v1 shipped)

**Remaining:** tenant-specific PII vocabularies beyond the default patterns
(Emirates ID, email, phone, Luhn cards); content moderation (toxicity)
stays out of scope for the framework.

---

## Appendix — Lessons (do not repeat)

Operational lessons distilled from past phases; full incident context in
`Product_Archive.md`.

- **Groq 429 retry needs FULL JITTER** — `(2**attempt)*5 + random.uniform(0, 3)`.
  A bare `2**n * 5` gives concurrent CI jobs identical waits; they retry in
  lockstep and re-saturate the rate window. Now baked into
  `scripts/cost_router.py`.
- **`# fail-open:` convention + global-copy drift** — the pre-commit hook
  executes the GLOBAL `~/.agent-framework/scripts/check_bare_except.py`,
  not the repo copy; always sync both when changing checker behavior. The
  one accepted suppression form is `# fail-open: <reason>`
  (`# noqa: bare-except` was retired — ruff rejects unknown noqa codes).
- **Graceful skip = exit 0** — `return 2` from `run_scorecard()` still
  fails the CI step; "skip gracefully on infra errors" requires `0`.
- **Test/code skew** — when changing a return value, update the test in the
  same commit; CI catches the skew if they ship separately.
- **Cloud SQL from Cloud Run** — use the Auth Proxy
  (`--add-cloudsql-instances`, Unix-socket `DATABASE_URL`), never
  `sslmode=no-verify`; grant the Compute SA `roles/cloudsql.client` and
  `roles/secretmanager.secretAccessor` per secret.
- **WIF attribute condition is one expression** — adding a repo means
  updating `==` to `in [...]`, or the new repo gets
  `unauthorized_client: rejected by attribute condition`.
- **oil-price-demo: cherry-pick, don't rebase** — the post-commit hook
  regenerates the Knowledge Graph on every git operation; rebasing dozens
  of commits fires it each step and blocks the rebase with unstaged changes.
  *Update 2026-07-21:* `AGENT_KG_DEFER=1 git rebase ...` now skips the
  per-step rebuild (run `python3 scripts/map_codebase.py` once afterwards),
  and the walk itself is incremental (unchanged files skipped by mtime) —
  rebase is safe again with the guard set.
