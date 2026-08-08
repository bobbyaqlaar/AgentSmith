# AgentSmith — Remaining To-Do Items

**Last reviewed:** 2026-07-29 (post-1.1.0 release + cross-repo review)

> **Scope:** this document owns only *not-yet-done* work: the active item and
> confirmed future gaps with their trigger conditions. Completed build history
> lives in `Product_Archive.md`; the formal specification is `SPECS.md`;
> operator procedures are `OPERATIONS.md`; release notes are `CHANGELOG.md`.
>
> If an entry here says something is missing, check it still is — this file
> spent a week claiming the testbed deploy had not started, six days after it
> had.

## Current state (2026-07-29)

**v1.1.1 is released.** v1.1.0 was the first actually-published version (1.0.0
was documented but never tagged, so no tenant could pin); v1.1.1 fixed the
install path itself — the bootstrap script and its `.sha256` had never been
release assets, so the documented `curl … | bash` 404'd at every version, and
silently, because that pipeline exits 0 on a 404.

Both suites are green: `python3 -m pytest -q` here and in `../KYC_Sentinel`.
No count is quoted — one was, and went stale three times in a single working
session. KYC Sentinel's strict security harness and adversarial eval gate are
green in CI; the three judge-backed gates skip until the judge has credit.

The **KYC Sentinel testbed tenant** (`../KYC_Sentinel`) is built, pushed,
CI-green and deployed as a GCP staging smoke job — full history in
`Product_Archive.md` "T1–T4". Everything code-side is done.

**The one open build item is running it against real backends** — see below.

---

## Active: KYC Sentinel "Running live" 🟡 NOT STARTED

**Goal:** take the tenant from offline/smoke-job to serving real traffic, so
the observability, HITL and promotion loops are exercised end-to-end rather
than asserted.

**Trigger:** fired — everything upstream of it is done.

**Blocked on:** standing up infrastructure and providing credentials. Not a
code blocker; deliberately deferred when the deploy pipeline was proven.

**What it needs** (from `KYC_Sentinel/DEVLOG.md` 2026-07-22):

1. Cloud SQL (`BUDGET_BACKEND=postgres`, `IDEMPOTENCY_BACKEND=postgres`),
   a Temporal server, Ollama for the sovereign `intake` route, and Phoenix.
2. Real provider keys: `ANTHROPIC_API_KEY_JUDGE` (the judge route's declared
   variable — setting it also turns on the three judge-backed eval gates),
   `ANTHROPIC_API_KEY`, `GROQ_API_KEY`.
3. Swap `cd-staging.yml`'s Cloud Run **Job** for a `gcloud run deploy` of
   `worker.py` as a long-running service (`--no-cpu-throttling
   --min-instances=1`, OPERATIONS.md §4), pointed at the real
   `TEMPORAL_ADDRESS`.
4. Then, in order: Phoenix/Ops Portal wiring → widget embed → first HITL
   round-trip through the portal → shadow-eval sampling on → first production
   golden case promoted.

Append progress to `KYC_Sentinel/DEVLOG.md` as you go.

---

## Demo publication (LinkedIn / Substack / Medium) 🟡 NOT STARTED

**Subject: KYC Sentinel**, not oil-price-demo. This file previously carried two
contradictory versions of this item; oil-price-demo was superseded as the demo
tenant when the purpose-built testbed was built.

**Trigger:** partially fired. The framework story and the tenant build are
publishable now; the operational screenshots (live Phoenix traces, a real HITL
round-trip) need "Running live" above.

**Article content:**

1. The framework architecture — Ten Pillars, multi-agent, eval scorecard.
2. Building KYC Sentinel: why KYC is the domain where compliance features are
   load-bearing rather than decorative (`docs/testbed-tenant-spec.md` opening).
3. What building a tenant found in the framework — G1–G10, then the 1.1.0
   review findings. The honest version of this is the most useful part: a HITL
   gate that could approve without a human, a security harness grading the
   wrong repo, a "graceful skip" that failed CI.
4. CI/CD: GitHub Actions → GCP Cloud Run via WIF (keyless).
5. Screenshots: Phoenix traces, Ops Portal, HITL DLQ flow, eval scorecard.

**Source material:** `Product_Archive.md` (build history, use as structure),
`README.md` (intro), `CHANGELOG.md` 1.1.0 (what the review found).

**Open cost:** Cloud SQL `temporal-pg` (~$7–10/month) and `temporal-server`
Cloud Run (min-instances=1) in `agentsmith-500916` are still live from the
oil-price-demo work. Either reuse them for KYC Sentinel's "Running live" or
tear them down — they are currently billing for nothing. Owner: Bobby.

---

Each future item records a **trigger condition** (the concrete signal that
means "build this now," not a calendar date), so a future session can decide
whether the trigger has fired instead of re-litigating whether the gap matters.

**Settled design decisions (do not re-open without a concrete reason):**
- MCP integration stays tenant-owned (BYO) — the framework ships no MCP
  client/server. Rationale in SPECS.md §4a.
- LLM self-correction is a separate opt-in method
  (`run_with_self_correction`), never inserted in front of the human DLQ path.
- The default model registry is local-only. Cloud tiers are a deliberate
  per-tenant opt-in, not something a budget breach can reach.

---

## Known gaps carried forward from the 1.1.0 review

Small, specific, and deliberately not fixed in that release.

- **`SEC-TOOL-001` verifies the mechanism, not your allowlist.** Its runner
  smoke-tests `ToolRegistry` deny-by-default against the shipped *template*,
  so a tenant's green SEC-TOOL-001 says the enforcement works — not that the
  tenant's own `tool_allowlist.yaml` is sane. **Trigger:** an auditor reads the
  evidence pack as a statement about the tenant's tools.
- ~~**12 of 23 `SEC-*` controls have no runner**~~ — **closed.** All are bound.
  The last four (`audit_hmac`, `dlq_check`, `sovereign_smoke`, `rag_poison`)
  were closed by separating the claim that needs infrastructure from the claim
  that does not, rather than by relabelling anything: HMAC tamper-evidence is
  provable offline and append-only enforcement is a database trigger, so the
  latter became **`SEC-AUDIT-002`** and is the one remaining declared gap. An
  undeclared gap — `met`/`partial` with no runner — fails `--strict`.
  Live status: `docs/security-framework-map.md`.
- **`agency_manifest` is authored but ungraded** — both the framework's and
  KYC's manifests are real content that nothing validates (see above).
- **`.env.swp`** — an orphaned vim swap file at the repo root, gitignored. Left
  in place because it may hold unsaved `.env` edits; delete once you're sure.
- **`scripts/verify_ttft.py:21`** — unused `from pathlib import Path`, flagged
  by ruff. Its sibling import carries a deliberate `noqa`, so the pair was left
  alone rather than half-changed.

---

## Future Phases — confirmed gaps, not yet scheduled

### Compliance gap status boards (pointers, not copies)

Live status for the two compliance tracks is maintained in one place each — do
**not** duplicate their tables here:

- **UAE Regulatory:** [`docs/uae-regulatory.md`](./docs/uae-regulatory.md) +
  [`docs/iso-42001-control-map.md`](./docs/iso-42001-control-map.md). Still
  open there: live verification against a *named* UAE sovereign API (beyond the
  verified Ollama Falcon 3 pattern), and org-level certification work (never
  framework-owned).
  **Trigger:** a bid requires live sovereign-endpoint verification, or an
  auditor demands a licensed clause-ID matrix beyond the thematic pack.
- **Enterprise Delivery Model:**
  [`docs/delivery-model.md`](./docs/delivery-model.md). v1 soft pack shipped.
  Still open: hard-fail enterprise mode; auto-inject `delivery.*` defaults from
  `ai-tenant-init`; a CD step uploading the evidence pack as a release artifact.
  **Trigger:** an org wants promote blocked when a platform isn't approved.

### Tool Orchestration — provider function-calling wire-up

**Shipped:** `runtime/tool_registry.py` (`@tool` + YAML allowlist,
`SEC-TOOL-001`, tenant-attributed spans). MCP stays **bring-your-own**.

**Remaining gap:** `llm_gateway.complete()` still does not emit provider
function-calling request fields — the registry is allowlist/schema extraction,
not a tool-choice runtime.

**Trigger:** a tenant needs the LLM to choose among tools dynamically inside
the gateway request, not only fixed activity sequences.

### Perception & Input Parsing — prompt templating

**Shipped:** `runtime/structured_output.py` (`parse_llm_json`,
`SEC-OUTPUT-001`).

**Remaining gap:** no reusable prompt-template engine; prompts are inline
f-strings (KYC Sentinel has four such prompts across its agents).

**Trigger:** 2+ real call sites sharing the same prompt structure.

**Fix sketch:** `runtime/prompt_templates.py` — a minimal Jinja2 or
`string.Template` wrapper.

### Memory / RAG — remaining extensions (v1 shipped)

Shipped: `conversation_memory.py`, `embeddings.py`, `vector_store.py`
(memory / pgvector). See [`docs/rag-memory.md`](./docs/rag-memory.md).

**Remaining:** summarization eviction; auto-RAG in the gateway; ingest/chunk
CLI; a live pgvector CI job (the extension is often absent in bare Postgres).

**Trigger:** a tenant needs summarization or gateway-native retrieve.

### HITL self-correction — remaining extensions (v1 shipped)

**Remaining:** tenant-specific policies for which error classes opt in.
Multi-turn planner/tool-choice correction stays out of scope.

### Eval suites — remaining extensions (v1 shipped)

- **Hallucination:** expand golden cases beyond seed pairs; a human review UI
  for flagged cases.
- **Fairness:** domain-specific sets beyond seed pairs; statistical
  disparate-impact metrics beyond judge + pair parity.
- **TTFT:** portal chat UI streaming; TTFT on the non-stream path (not
  measurable without a fake first token). Not wired into KYC Sentinel's CI —
  it needs a live streaming provider.

### Input guardrail — remaining extensions (v1 shipped)

**Remaining:** tenant-specific PII vocabularies beyond the default patterns
(Emirates ID, email, phone, Luhn cards). Content moderation (toxicity) stays
out of framework scope — tenants declare a `moderation.hook`.

### Package rename — `runtime` → `agentsmith_runtime`

The distribution is `agentsmith-runtime` but imports as the generic top-level
`runtime`, which could collide in a crowded virtualenv. Noted in
`pyproject.toml`.

**Trigger:** a real collision, or the next major version — it breaks every
`from runtime.X import Y` in every tenant at once, so it is a 2.0.0 change.

---

## Appendix — Lessons (do not repeat)

Operational lessons distilled from past phases; full incident context in
`Product_Archive.md` and `CHANGELOG.md`.

- **A test double must never be more capable than the real thing.** KYC
  Sentinel's original fake gateway aliased `complete_stream` to `complete`,
  hiding a production crash on the analyst's own route. `runtime/testing.py`'s
  shipped double now refuses to stream what the real gateway can't.
- **A guard assertion inside the `try` it guards is not a guard.** Two F-scenario
  drivers raised `AssertionError` inside a block caught by
  `except Exception`, so they reported their control proven while it was
  broken — through CI and a Cloud Run smoke job.
- **Config that is read from two places will disagree.** There were four
  copies of "which model is the architect tier", a judge id in a constant
  *and* in models.yaml, and a security pack that was a byte-copy of its own
  template. Every one had drifted. Read from one source; guard it with a test.
- **cwd-relative vs install-relative is a real distinction.** The security
  harness resolved the tenant pack from its install location, so every tenant
  graded the framework's pack. Two roots that coincide during self-test hide
  this completely.
- **"Skip gracefully" means exit 0.** `return 2` from `run_scorecard()` still
  failed the CI step, so every fresh tenant went red for not yet having a
  golden dataset. This lesson was recorded here and applied to only one of two
  call sites for months.
- **A CI callee must ship with its caller.** `ci-python-fastapi.yml`
  referenced `eval-security.yml`, which `ai-tenant-init` never copied — GitHub
  rejects the whole workflow as invalid, not just the missing job.
- **GitHub Actions rejects YAML anchors.** They parse fine locally and fail on
  the runner.
- **Groq 429 retry needs FULL JITTER** — `(2**attempt)*5 + random.uniform(0, 3)`.
  A bare `2**n * 5` gives concurrent CI jobs identical waits. Baked into
  `scripts/cost_router.py`.
- **`# fail-open:` convention + global-copy drift** — the pre-commit hook
  executes the GLOBAL `~/.agent-framework/scripts/check_bare_except.py`, not
  the repo copy; sync both when changing checker behaviour.
- **Cloud SQL from Cloud Run** — use the Auth Proxy
  (`--add-cloudsql-instances`, Unix-socket `DATABASE_URL`), never
  `sslmode=no-verify`; grant the Compute SA `roles/cloudsql.client` and
  `roles/secretmanager.secretAccessor` per secret.
- **New GCP projects grant the default compute SA nothing.** Cloud Run
  `--source` deploys use it via Cloud Build; it needs
  `roles/storage.objectViewer`, `roles/artifactregistry.writer`,
  `roles/logging.logWriter` before a first deploy will work.
- **WIF attribute condition is one expression** — adding a repo means updating
  `==` to `in [...]`, or the new repo gets
  `unauthorized_client: rejected by attribute condition`.
- **oil-price-demo: cherry-pick, don't rebase** — the post-commit hook
  regenerates the Knowledge Graph on every git operation. `AGENT_KG_DEFER=1 git
  rebase ...` now skips the per-step rebuild (run `python3
  scripts/map_codebase.py` once afterwards).
